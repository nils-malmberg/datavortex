"""Cache des résultats coûteux et idempotents (Phase 10.1, §3.5).

Le profil détaillé d'un fichier de 3,2 millions de lignes demande une minute de
calcul. Le recalculer parce que l'utilisateur est revenu sur l'onglet est du
temps perdu deux fois : pour lui, et pour le serveur qui ne fait rien d'autre
pendant ce temps.

La justesse d'un cache tient entièrement à son invalidation. Ici, la clé
contient `session.data_version`, que `Session.__setattr__` incrémente à chaque
changement de données : un résultat calculé avant un filtre porte une version
différente de celle demandée après, et n'est donc jamais servi à sa place. Les
entrées périmées ne sont pas effacées activement — elles deviennent
inatteignables, et le balayage par taille les évacue.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable, Optional

# Durée de vie d'une entrée. Généreuse : l'invalidation réelle vient du numéro
# de version des données, le TTL ne sert qu'à borner la mémoire d'une session
# oubliée. Une session expire de toute façon au bout d'une heure d'inactivité.
DEFAULT_TTL_SECONDS = 60 * 60

# Nombre maximal d'entrées conservées, toutes sessions confondues. Chaque
# entrée est un résultat JSON-sérialisable de quelques dizaines de kilo-octets
# au plus : ce plafond borne l'empreinte du cache à quelques dizaines de Mo.
MAX_ENTRIES = 128


def _params_fingerprint(params: Optional[dict]) -> str:
    if not params:
        return "-"
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=8).hexdigest()


class ResultCache:
    """Cache mémoire à clé (session, version des données, opération, paramètres)."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, max_entries: int = MAX_ENTRIES) -> None:
        self._entries: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        # Les routes synchrones de FastAPI s'exécutent dans un pool de threads :
        # deux requêtes peuvent écrire ici en même temps.
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def key(self, session_id: str, data_version: int, operation: str, params: Optional[dict] = None) -> str:
        return f"{session_id}:{data_version}:{operation}:{_params_fingerprint(params)}"

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            value, stored_at = entry
            # Horloge monotone : `time.time()` peut reculer (NTP) et n'avance
            # que par pas de ~16 ms sur Windows, où une entrée à TTL nul
            # semblait alors encore fraîche. `>=` : une entrée exactement à
            # l'âge du TTL est périmée.
            if time.monotonic() - stored_at >= self._ttl:
                del self._entries[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._entries) >= self._max_entries:
                self._evict_locked()
            self._entries[key] = (value, time.monotonic())

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        """Renvoie l'entrée en cache, ou calcule et mémorise le résultat.

        Le calcul est délibérément fait hors verrou : deux requêtes simultanées
        sur une même clé froide calculeront deux fois plutôt que de se bloquer
        l'une l'autre pendant une minute. Le résultat étant déterministe, la
        seule conséquence est un calcul redondant dans un cas rare.
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value)
        return value

    def invalidate_session(self, session_id: str) -> None:
        """Oublie tout ce qui concerne une session (fermeture, expiration)."""
        prefix = f"{session_id}:"
        with self._lock:
            for key in [k for k in self._entries if k.startswith(prefix)]:
                del self._entries[key]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._entries),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 3) if total else 0.0,
            }

    def _evict_locked(self) -> None:
        """Évacue les entrées les plus anciennes. Appelé verrou tenu."""
        oldest = sorted(self._entries.items(), key=lambda item: item[1][1])
        for key, _ in oldest[: max(1, len(oldest) // 4)]:
            del self._entries[key]


# Instance partagée par toute l'application.
cache = ResultCache()
