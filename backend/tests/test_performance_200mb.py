"""Phase 10.1 : mesures de bout en bout sur un fichier de 200 Mo.

Ces tests demandent un jeu de données de 3,2 millions de lignes que le dépôt
ne versionne pas (210 Mo). Ils sont donc ignorés tant qu'il n'existe pas :

    cd backend
    python scripts/generate_test_data.py --rows 3200000 --out test_data/large_200mb.csv
    pytest tests/test_performance_200mb.py -v

Les seuils sont ceux de la spec Phase 10.1, élargis d'un facteur pour tolérer
une machine chargée : ils servent à détecter une régression d'un ordre de
grandeur, pas à départager 3,1 s de 3,4 s. Les mesures de référence figurent
dans specs/PHASE_10_1_BENCHMARK_RESULTS.md.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.cache import cache
from app.main import app
from app.session_store import store

DATASET = Path(__file__).resolve().parent.parent / "test_data" / "large_200mb.csv"

pytestmark = pytest.mark.skipif(
    not DATASET.exists(),
    reason=f"jeu de données absent : {DATASET} (voir la docstring pour le générer)",
)

client = TestClient(app)


@pytest.fixture(scope="module")
def _loaded_session():
    """Charge le fichier de 210 Mo une seule fois pour tout le module."""
    cache.clear()
    raw = DATASET.read_bytes()
    resp = client.post("/api/upload", files={"file": (DATASET.name, raw, "text/csv")})
    assert resp.status_code == 200, resp.text[:300]
    sid = resp.json()["session_id"]
    assert client.post("/api/parse", json={"session_id": sid, "separator": ","}).status_code == 200
    return store.get(sid)


@pytest.fixture
def session_id(_loaded_session):
    """Réinscrit la session avant chaque test.

    Le `conftest.py` du dossier vide le store entre chaque test pour les
    isoler. C'est la bonne règle générale, mais ici recharger 210 Mo dix fois
    ferait durer la suite plusieurs minutes pour mesurer exactement la même
    chose : la session est donc reconstituée telle quelle.
    """
    store._sessions[_loaded_session.session_id] = _loaded_session
    return _loaded_session.session_id


def _timed(call):
    start = time.perf_counter()
    resp = call()
    duration = time.perf_counter() - start
    assert resp.status_code == 200, resp.text[:300]
    return resp, duration


def test_upload_and_parse_under_20s():
    """Chargement complet d'un fichier de 210 Mo (upload + analyse)."""
    cache.clear()
    raw = DATASET.read_bytes()
    start = time.perf_counter()
    resp = client.post("/api/upload", files={"file": (DATASET.name, raw, "text/csv")})
    sid = resp.json()["session_id"]
    parsed = client.post("/api/parse", json={"session_id": sid, "separator": ","})
    duration = time.perf_counter() - start

    assert parsed.status_code == 200
    assert parsed.json()["n_rows"] == 3_200_000
    client.delete(f"/api/session/{sid}")
    assert duration < 20, f"chargement en {duration:.1f}s"


def test_preview_under_1s(session_id):
    """L'aperçu ne doit jamais parcourir le fichier entier."""
    _, duration = _timed(lambda: client.get(f"/api/data/{session_id}/preview"))
    assert duration < 1.0, f"aperçu en {duration:.2f}s"


def test_paginated_rows_under_5s(session_id):
    _, duration = _timed(lambda: client.get(f"/api/data/{session_id}/rows?offset=0&limit=100"))
    assert duration < 5.0, f"page en {duration:.2f}s"


def test_second_page_is_cached_and_fast(session_id):
    """Les propriétés du jeu de données ne sont calculées qu'une fois."""
    client.get(f"/api/data/{session_id}/rows?offset=0&limit=100")
    _, duration = _timed(lambda: client.get(f"/api/data/{session_id}/rows?offset=100&limit=100"))
    assert duration < 1.0, f"page suivante en {duration:.2f}s"


def test_groupby_under_3s(session_id):
    _, duration = _timed(lambda: client.post("/api/groupby", json={
        "session_id": session_id,
        "group_by": ["department"],
        "aggregations": [{"column": "salary", "func": "mean"}],
    }))
    assert duration < 3.0, f"groupby en {duration:.2f}s"


def test_filter_under_3s(session_id):
    _, duration = _timed(lambda: client.post(f"/api/data/{session_id}/filter", json={
        "filter": {"type": "condition", "column": "salary", "operator": "gt", "value": 50000},
    }))
    assert duration < 3.0, f"filtre en {duration:.2f}s"
    client.post(f"/api/data/{session_id}/filter", json={"filter": None})


def test_stats_under_20s_then_instant_from_cache(session_id):
    _, first = _timed(lambda: client.get(f"/api/stats/{session_id}"))
    _, second = _timed(lambda: client.get(f"/api/stats/{session_id}"))
    assert first < 20.0, f"stats en {first:.1f}s"
    assert second < 0.5, f"stats en cache en {second:.2f}s"


def test_profile_under_30s_and_sampled(session_id):
    """Le profil échantillonne au-delà d'un demi-million de lignes, et le dit."""
    resp, duration = _timed(lambda: client.get(f"/api/profile/{session_id}/detailed"))
    sampling = resp.json()["sampling"]
    assert sampling["sampled"] is True
    assert sampling["rows_analyzed"] < sampling["total_rows"]
    assert duration < 30.0, f"profil en {duration:.1f}s"


def test_scatter_payload_stays_small(session_id):
    """Une figure transporte ses données : elle doit rester téléchargeable.

    Sans échantillonnage, un nuage de points sur 3,2 millions de lignes pesait
    36 Mo de JSON et bloquait l'onglet du navigateur à la désérialisation.
    """
    resp, duration = _timed(lambda: client.post("/api/plot/advanced", json={
        "session_id": session_id, "plot_type": "scatter", "x": "age", "y": "salary",
    }))
    megabytes = len(resp.content) / 1024 / 1024
    assert megabytes < 5, f"figure de {megabytes:.1f} Mo"
    assert duration < 5.0, f"figure en {duration:.2f}s"


def test_subplot_grid_payload_stays_small(session_id):
    resp, duration = _timed(lambda: client.post("/api/plot/subplots", json={
        "session_id": session_id, "rows": 2, "cols": 2,
        "subplots": [
            {"plot_type": "scatter", "x": "age", "y": "salary"},
            {"plot_type": "histogram", "y": "score"},
            {"plot_type": "box", "y": "salary"},
            {"plot_type": "bar", "x": "department", "y": "score"},
        ],
    }))
    megabytes = len(resp.content) / 1024 / 1024
    assert megabytes < 10, f"grille de {megabytes:.1f} Mo"
    assert duration < 5.0, f"grille en {duration:.2f}s"
