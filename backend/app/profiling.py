"""Profilage optionnel des opérations coûteuses (Phase 10, §4).

Désactivé par défaut : cProfile et tracemalloc ajoutent un coût réel à chaque
appel (souvent 2 à 5x plus lent), ce qui n'a rien à faire d'actif en
permanence pour un module dont le but est justement la performance. Ces
décorateurs deviennent des no-ops tant que `DATAVORTEX_PROFILE=1` n'est pas
positionné dans l'environnement — un développeur qui cherche pourquoi une
agrégation particulière est lente l'active ponctuellement, en local.

Ne couvre que les fonctions synchrones : les deux points d'application visés
(`_run_groupby_for`, `get_advanced_stats`) sont des routes `def` classiques.
"""
from __future__ import annotations

import cProfile
import functools
import io
import logging
import os
import pstats
import tracemalloc

logger = logging.getLogger("datavortex.profiling")

_ENABLED = os.environ.get("DATAVORTEX_PROFILE", "") == "1"


def profile_operation(func):
    """Journalise les 10 appels les plus coûteux (temps cumulé) d'un appel."""
    if not _ENABLED:
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            return func(*args, **kwargs)
        finally:
            profiler.disable()
            buffer = io.StringIO()
            pstats.Stats(profiler, stream=buffer).sort_stats("cumulative").print_stats(10)
            logger.info("Profil %s :\n%s", func.__name__, buffer.getvalue())

    return wrapper


def memory_tracker(func):
    """Journalise le pic mémoire Python (tracemalloc) d'un appel."""
    if not _ENABLED:
        return func

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        try:
            return func(*args, **kwargs)
        finally:
            _current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            logger.info("%s : %.1f Mo (pic tracemalloc)", func.__name__, peak / 1024 / 1024)

    return wrapper
