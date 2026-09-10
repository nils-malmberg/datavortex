"""Métriques de performance et de mémoire (Phase 9, §6).

Sur un gros fichier, « c'est lent » n'est pas un diagnostic. Ces indicateurs —
durée, débit, empreinte mémoire du processus — accompagnent les réponses des
routes coûteuses pour que le ralentissement soit attribuable à une opération
précise plutôt qu'à l'application en général.
"""
from __future__ import annotations

import time
from typing import Any, Optional

try:  # pragma: no cover - psutil absent ne doit jamais empêcher le serveur de démarrer
    import psutil

    _process = psutil.Process()
except Exception:  # pragma: no cover
    psutil = None
    _process = None

SERVER_START_TIME = time.time()


def memory_usage() -> dict[str, Any]:
    """Empreinte mémoire du processus, en mégaoctets."""
    if _process is None:  # pragma: no cover
        return {"available": False}
    info = _process.memory_info()
    usage: dict[str, Any] = {
        "available": True,
        "rss_mb": round(info.rss / 1024 / 1024, 1),
        "vms_mb": round(info.vms / 1024 / 1024, 1),
    }
    try:
        system = psutil.virtual_memory()
        usage["system_total_mb"] = round(system.total / 1024 / 1024, 1)
        usage["system_available_mb"] = round(system.available / 1024 / 1024, 1)
        usage["system_percent_used"] = system.percent
    except Exception:  # pragma: no cover
        pass
    return usage


def uptime_seconds() -> float:
    return round(time.time() - SERVER_START_TIME, 1)


class Timer:
    """Chronomètre de bloc, utilisé pour annoter les réponses coûteuses.

        with Timer() as t:
            result = heavy_call()
        response["metrics"] = t.metrics(rows=len(result))
    """

    def __init__(self) -> None:
        self.start = 0.0
        self.end: Optional[float] = None

    def __enter__(self) -> "Timer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        self.end = time.perf_counter()

    @property
    def elapsed(self) -> float:
        end = self.end if self.end is not None else time.perf_counter()
        return end - self.start

    def metrics(self, rows: Optional[int] = None, engine: Optional[str] = None) -> dict[str, Any]:
        duration = self.elapsed
        payload: dict[str, Any] = {"duration_seconds": round(duration, 4)}
        if rows is not None:
            payload["rows_processed"] = int(rows)
            # Sous la milliseconde, le débit calculé est du bruit de mesure.
            if duration > 0.001:
                payload["throughput_rows_per_sec"] = int(rows / duration)
        if engine is not None:
            payload["engine"] = engine
        return payload
