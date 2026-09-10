"""Exécution en arrière-plan des opérations lourdes (Phase 9).

Une agrégation sur 500 000 lignes prend plusieurs secondes. Tant qu'elle est
calculée dans le gestionnaire de route, la requête HTTP reste ouverte et
l'interface se fige. Ce module découple les deux : la route enregistre la tâche
et rend immédiatement un `task_id`, le client interroge ensuite son état.

**Point d'attention** : le calcul est confié à un pool de threads, pas à une
coroutine. Un `asyncio.create_task()` autour de code pandas synchrone ne rend
jamais la main à la boucle d'événements — le serveur entier resterait bloqué,
y compris pour les autres sessions. Seul le passage par un thread libère
réellement la boucle. C'est aussi ce qui permet à Polars, qui relâche le GIL
pendant ses calculs, de tirer parti des cœurs disponibles.
"""
from __future__ import annotations

import asyncio
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Les tâches terminées restent consultables un moment : le client peut mettre du
# temps à venir chercher son résultat (onglet en arrière-plan, réseau lent).
TASK_TTL_SECONDS = 10 * 60
MAX_TASKS = 200
# Borne le parallélisme : au-delà, des calculs concurrents se disputent la RAM,
# ce qui est précisément le risque à éviter sur de gros fichiers.
MAX_WORKERS = 4

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    kind: str
    status: str = STATUS_PENDING
    result: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    http_status: int = 500
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancelled: bool = False

    def duration_seconds(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at if self.finished_at is not None else time.time()
        return end - self.started_at

    def to_status_dict(self) -> dict[str, Any]:
        """État sérialisable, sans le résultat (parfois volumineux)."""
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "duration_seconds": self.duration_seconds(),
        }


class TaskRegistry:
    """Registre en mémoire des tâches, protégé par un verrou.

    Le verrou est indispensable : les tâches s'exécutent dans des threads, mais
    les routes qui les consultent tournent dans la boucle d'événements.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="datavortex-task")

    def submit(self, kind: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Task:
        """Enregistre une tâche et lance son exécution dans un thread."""
        self._sweep()
        task = Task(task_id=str(uuid.uuid4()), kind=kind)
        with self._lock:
            if len(self._tasks) >= MAX_TASKS:
                # Le registre est plein de tâches encore vivantes : on écarte la
                # plus ancienne plutôt que de refuser le travail.
                oldest = min(self._tasks.values(), key=lambda t: t.created_at)
                del self._tasks[oldest.task_id]
            self._tasks[task.task_id] = task

        self._executor.submit(self._run, task, fn, args, kwargs)
        return task

    def _run(self, task: Task, fn: Callable[..., Any], args: tuple, kwargs: dict) -> None:
        if task.cancelled:
            task.status = STATUS_CANCELLED
            task.finished_at = time.time()
            return

        task.status = STATUS_RUNNING
        task.started_at = time.time()
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - toute erreur doit remonter au client
            task.error = str(exc)
            # Les erreurs métier portent un code et un statut HTTP qu'il faut
            # préserver, sinon le client affiche « erreur interne » à la place
            # d'un message explicite (« trop de groupes », « colonne inconnue »).
            task.error_code = getattr(exc, "code", None) or exc.__class__.__name__
            task.http_status = getattr(exc, "status_code", 500)
            task.status = STATUS_ERROR
            traceback.print_exc()
        else:
            if task.cancelled:
                task.status = STATUS_CANCELLED
            else:
                task.result = result
                task.status = STATUS_DONE
        finally:
            task.finished_at = time.time()

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """Marque une tâche comme annulée.

        Un calcul déjà lancé n'est pas interrompu — pandas et Polars n'offrent
        pas de point d'annulation — mais son résultat est écarté et la tâche
        cesse d'occuper le registre. Une tâche encore en attente, elle, ne
        démarrera pas.
        """
        task = self.get(task_id)
        if task is None or task.status in (STATUS_DONE, STATUS_ERROR, STATUS_CANCELLED):
            return False
        task.cancelled = True
        return True

    def _sweep(self) -> None:
        """Purge les tâches terminées au-delà du TTL."""
        now = time.time()
        with self._lock:
            expired = [
                tid
                for tid, t in self._tasks.items()
                if t.finished_at is not None and now - t.finished_at > TASK_TTL_SECONDS
            ]
            for tid in expired:
                del self._tasks[tid]

    def stats(self) -> dict[str, int]:
        with self._lock:
            tasks = list(self._tasks.values())
        counts: dict[str, int] = {}
        for task in tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        return {"total": len(tasks), **counts}

    def clear(self) -> None:
        """Vide le registre (utilisé pour isoler les tests)."""
        with self._lock:
            self._tasks.clear()


registry = TaskRegistry()


async def wait_for(task_id: str, timeout: float = 30.0, poll_interval: float = 0.02) -> Optional[Task]:
    """Attend la fin d'une tâche sans bloquer la boucle d'événements.

    Sert aux tests et aux appels internes ; le client HTTP, lui, interroge la
    route de statut à son propre rythme.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = registry.get(task_id)
        if task is None:
            return None
        if task.status in (STATUS_DONE, STATUS_ERROR, STATUS_CANCELLED):
            return task
        await asyncio.sleep(poll_interval)
    return registry.get(task_id)
