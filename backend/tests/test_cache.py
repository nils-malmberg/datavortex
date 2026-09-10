"""Phase 10.1 : cache de résultats et invalidation par version des données.

Un cache mal invalidé est pire que pas de cache : il sert en silence un
résultat faux. Ces tests couvrent chaque manière de modifier les données d'une
session — filtre, colonne calculée, transformation, opération sur colonnes,
re-parsing — et vérifient que le résultat suivant est bien recalculé.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.cache import ResultCache, cache
from app.main import app
from app.session_store import Session

client = TestClient(app)

CSV_CONTENT = b"name,age,score\nAlice,30,85.5\nBob,25,90.0\nCharlie,35,78.2\nDiana,28,88.0\n"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _session():
    resp = client.post("/api/upload", files={"file": ("t.csv", CSV_CONTENT, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


# --- Mécanique du cache ----------------------------------------------------


def test_hit_and_miss_counted():
    local = ResultCache()
    key = local.key("s", 0, "op")
    assert local.get(key) is None
    local.set(key, {"value": 1})
    assert local.get(key) == {"value": 1}
    assert local.stats()["hits"] == 1
    assert local.stats()["misses"] == 1


def test_key_changes_with_data_version():
    local = ResultCache()
    assert local.key("s", 1, "stats") != local.key("s", 2, "stats")


def test_key_changes_with_params():
    local = ResultCache()
    assert local.key("s", 1, "stats", {"method": "pearson"}) != local.key("s", 1, "stats", {"method": "kendall"})


def test_get_or_compute_calls_once():
    local = ResultCache()
    calls = []

    def compute():
        calls.append(1)
        return "value"

    key = local.key("s", 0, "op")
    assert local.get_or_compute(key, compute) == "value"
    assert local.get_or_compute(key, compute) == "value"
    assert len(calls) == 1


def test_expired_entry_is_a_miss():
    local = ResultCache(ttl_seconds=0)
    key = local.key("s", 0, "op")
    local.set(key, "value")
    assert local.get(key) is None


def test_eviction_bounds_size():
    local = ResultCache(max_entries=8)
    for i in range(30):
        local.set(local.key("s", 0, f"op{i}"), i)
    assert local.stats()["entries"] <= 8


def test_invalidate_session_leaves_others_alone():
    local = ResultCache()
    local.set(local.key("a", 0, "op"), 1)
    local.set(local.key("b", 0, "op"), 2)
    local.invalidate_session("a")
    assert local.get(local.key("a", 0, "op")) is None
    assert local.get(local.key("b", 0, "op")) == 2


# --- Version des données ---------------------------------------------------


def test_assigning_tracked_fields_bumps_version():
    session = Session(session_id="s", filename="f", file_kind="csv", raw_bytes=b"", encoding="utf-8")
    before = session.data_version
    session.df = None
    assert session.data_version > before
    mid = session.data_version
    session.filtered_df = None
    session.active_filter = None
    assert session.data_version > mid


def test_untracked_field_does_not_bump_version():
    session = Session(session_id="s", filename="f", file_kind="csv", raw_bytes=b"", encoding="utf-8")
    before = session.data_version
    session.touch()
    session.separator = ";"
    assert session.data_version == before


# --- Invalidation de bout en bout ------------------------------------------


def _stats_rows(session_id):
    return client.get(f"/api/stats/{session_id}").json()["n_rows"]


def test_stats_served_from_cache_when_unchanged():
    session_id = _session()
    assert _stats_rows(session_id) == 4
    before = cache.stats()["hits"]
    assert _stats_rows(session_id) == 4
    assert cache.stats()["hits"] > before


def test_filter_invalidates_stats():
    session_id = _session()
    assert _stats_rows(session_id) == 4
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "age", "operator": "gt", "value": 27}},
    )
    assert _stats_rows(session_id) == 3


def test_created_column_invalidates_stats():
    """La création d'une colonne écrit *en place* : le cas qui échappe à __setattr__."""
    session_id = _session()
    before = client.get(f"/api/stats/{session_id}").json()
    assert "double_age" not in before["columns"]
    client.post(f"/api/data/{session_id}/columns", json={"name": "double_age", "formula": "{age} * 2"})
    after = client.get(f"/api/stats/{session_id}").json()
    assert "double_age" in after["columns"]


def test_column_transform_invalidates_stats():
    session_id = _session()
    client.get(f"/api/stats/{session_id}")
    resp = client.post(
        "/api/columns/transform",
        json={"session_id": session_id, "transform": "binning", "source": "age",
              "params": {"bins": 2}, "new_name": "age_bin"},
    )
    assert resp.status_code == 200
    assert "age_bin" in client.get(f"/api/stats/{session_id}").json()["columns"]


def test_column_operation_invalidates_stats():
    session_id = _session()
    client.get(f"/api/stats/{session_id}")
    resp = client.post("/api/columns/operation", json={"session_id": session_id, "op": "delete", "columns": ["score"]})
    assert resp.status_code == 200
    assert "score" not in client.get(f"/api/stats/{session_id}").json()["columns"]


def test_table_facts_invalidated_by_filter():
    """Les types/bornes du tableau sont mis en cache : ils doivent suivre le filtre."""
    session_id = _session()
    first = client.get(f"/api/data/{session_id}/rows?limit=10").json()
    assert first["total_rows"] == 4
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "age", "operator": "gt", "value": 27}},
    )
    second = client.get(f"/api/data/{session_id}/rows?limit=10").json()
    assert second["total_rows"] == 3


def test_deleting_session_clears_its_cache():
    session_id = _session()
    client.get(f"/api/stats/{session_id}")
    client.delete(f"/api/session/{session_id}")
    assert client.get(f"/api/stats/{session_id}").status_code == 404


def test_health_reports_cache_stats():
    body = client.get("/api/health").json()
    assert "cache" in body
    assert {"entries", "hits", "misses", "hit_rate"} <= set(body["cache"])
