"""Phase 10 : les décorateurs de profilage sont des no-ops sans DATAVORTEX_PROFILE=1."""
from __future__ import annotations

import importlib
import logging

import app.profiling as profiling_module


def _reload_with_env(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("DATAVORTEX_PROFILE", raising=False)
    else:
        monkeypatch.setenv("DATAVORTEX_PROFILE", value)
    return importlib.reload(profiling_module)


def test_profile_operation_is_noop_by_default(monkeypatch):
    mod = _reload_with_env(monkeypatch, None)

    def add(a, b):
        return a + b

    wrapped = mod.profile_operation(add)
    assert wrapped is add  # aucun wrapping : identité de fonction préservée


def test_memory_tracker_is_noop_by_default(monkeypatch):
    mod = _reload_with_env(monkeypatch, None)

    def add(a, b):
        return a + b

    wrapped = mod.memory_tracker(add)
    assert wrapped is add


def test_profile_operation_wraps_and_logs_when_enabled(monkeypatch, caplog):
    mod = _reload_with_env(monkeypatch, "1")

    @mod.profile_operation
    def add(a, b):
        return a + b

    with caplog.at_level(logging.INFO, logger="datavortex.profiling"):
        assert add(2, 3) == 5
    assert any("Profil add" in record.message for record in caplog.records)

    # Nettoyage : recharger sans la variable pour ne pas polluer les autres tests.
    _reload_with_env(monkeypatch, None)


def test_memory_tracker_wraps_and_logs_when_enabled(monkeypatch, caplog):
    mod = _reload_with_env(monkeypatch, "1")

    @mod.memory_tracker
    def allocate():
        return [0] * 1000

    with caplog.at_level(logging.INFO, logger="datavortex.profiling"):
        result = allocate()
    assert len(result) == 1000
    assert any("pic tracemalloc" in record.message for record in caplog.records)

    _reload_with_env(monkeypatch, None)
