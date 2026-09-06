"""Lecture tabulaire paginée (Phase 8) : tri, recherche, regroupement, pagination."""
import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _upload(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    resp = client.post("/api/upload", files={"file": ("data.csv", buf.getvalue().encode(), "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


@pytest.fixture()
def dataset():
    rng = np.random.default_rng(4)
    n = 500
    values = rng.normal(100, 10, n)
    values[:5] = [500.0, 480.0, -200.0, -190.0, 470.0]  # valeurs extrêmes
    df = pd.DataFrame({
        "id": np.arange(1, n + 1),
        "value": values,
        "category": rng.choice(["alpha", "beta", "gamma"], n),
        "label": [f"row_{i:04d}" for i in range(n)],
    })
    df.loc[10:19, "value"] = np.nan
    return df, _upload(df)


def _rows(session_id, **params):
    return client.get(f"/api/data/{session_id}/rows", params=params)


def test_pagination_returns_requested_slice(dataset):
    _, session_id = dataset
    body = _rows(session_id, offset=100, limit=25).json()
    assert body["shown_rows"] == 25
    assert body["offset"] == 100
    assert body["total_rows"] == 500
    assert body["rows"][0]["id"] == 101
    assert body["row_indices"][0] == 100


def test_pagination_last_page_is_partial(dataset):
    _, session_id = dataset
    body = _rows(session_id, offset=490, limit=25).json()
    assert body["shown_rows"] == 10


def test_page_size_bounds_enforced(dataset):
    _, session_id = dataset
    assert _rows(session_id, limit=0).status_code == 400
    assert _rows(session_id, limit=5000).status_code == 400


def test_sorting_ascending_and_descending(dataset):
    df, session_id = dataset
    ascending = _rows(session_id, sort_by="value", sort_dir="asc", limit=5).json()
    descending = _rows(session_id, sort_by="value", sort_dir="desc", limit=5).json()
    assert [r["value"] for r in ascending["rows"]] == sorted(r["value"] for r in ascending["rows"])
    assert ascending["rows"][0]["value"] == pytest.approx(df["value"].min())
    assert descending["rows"][0]["value"] == pytest.approx(df["value"].max())


def test_sorting_text_column(dataset):
    _, session_id = dataset
    body = _rows(session_id, sort_by="label", sort_dir="desc", limit=3).json()
    labels = [r["label"] for r in body["rows"]]
    assert labels == sorted(labels, reverse=True)


def test_sort_unknown_column_rejected(dataset):
    _, session_id = dataset
    resp = _rows(session_id, sort_by="inconnue")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COLUMN_NOT_FOUND"


def test_search_across_all_columns(dataset):
    df, session_id = dataset
    body = _rows(session_id, search="alpha").json()
    assert body["matched_rows"] == int((df["category"] == "alpha").sum())
    assert all(row["category"] == "alpha" for row in body["rows"])


def test_search_is_case_insensitive(dataset):
    _, session_id = dataset
    assert _rows(session_id, search="ALPHA").json()["matched_rows"] == _rows(session_id, search="alpha").json()["matched_rows"]


def test_search_scoped_to_one_column(dataset):
    _, session_id = dataset
    scoped = _rows(session_id, search="row_0001", search_column="label").json()
    assert scoped["matched_rows"] == 1


def test_search_without_match_returns_empty_page(dataset):
    _, session_id = dataset
    body = _rows(session_id, search="zzz_introuvable").json()
    assert body["matched_rows"] == 0
    assert body["rows"] == []


def test_grouping_makes_rows_contiguous_and_reports_counts(dataset):
    df, session_id = dataset
    body = _rows(session_id, group_by="category", limit=500).json()
    categories = [r["category"] for r in body["rows"]]
    # Un groupe ne doit apparaître qu'une seule fois dans la séquence.
    transitions = [c for i, c in enumerate(categories) if i == 0 or c != categories[i - 1]]
    assert len(transitions) == len(set(transitions))
    counts = {g["value"]: g["count"] for g in body["groups"]}
    assert counts == {k: int(v) for k, v in df["category"].value_counts().items()}


def test_grouping_and_sorting_combine(dataset):
    _, session_id = dataset
    body = _rows(session_id, group_by="category", sort_by="value", sort_dir="asc", limit=500).json()
    # À l'intérieur d'un groupe, les valeurs restent triées.
    by_group = {}
    for row in body["rows"]:
        by_group.setdefault(row["category"], []).append(row["value"])
    for values in by_group.values():
        clean = [v for v in values if v is not None]
        assert clean == sorted(clean)


def test_outlier_bounds_follow_tukey_rule(dataset):
    df, session_id = dataset
    bounds = _rows(session_id).json()["outlier_bounds"]
    clean = df["value"].dropna()
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    assert bounds["value"][0] == pytest.approx(q1 - 1.5 * iqr)
    assert bounds["value"][1] == pytest.approx(q3 + 1.5 * iqr)
    # Les valeurs extrêmes injectées tombent bien hors des bornes.
    assert 500.0 > bounds["value"][1] and -200.0 < bounds["value"][0]


def test_column_types_and_metadata_returned(dataset):
    _, session_id = dataset
    body = _rows(session_id).json()
    assert body["column_types"]["id"] == "integer"
    assert body["column_types"]["value"] == "float"
    assert body["column_types"]["category"] == "string"
    assert body["memory_usage_bytes"] > 0


def test_rows_respect_active_filter(dataset):
    _, session_id = dataset
    filtered = client.post("/api/filters/apply", json={
        "session_id": session_id,
        "filter": {"type": "condition", "column": "category", "operator": "eq", "value": "beta"},
    }).json()
    body = _rows(session_id).json()
    assert body["filtered"] is True
    assert body["total_rows"] == filtered["total_rows"]
    assert body["total_rows_unfiltered"] == 500
    assert all(row["category"] == "beta" for row in body["rows"])


def test_large_dataset_pagination_is_bounded():
    """Une page reste petite quelle que soit la taille du jeu de données."""
    rng = np.random.default_rng(9)
    n = 60_000
    df = pd.DataFrame({"id": np.arange(n), "v": rng.normal(0, 1, n), "c": rng.choice(list("abcd"), n)})
    session_id = _upload(df)
    body = _rows(session_id, offset=55_000, limit=100).json()
    assert body["total_rows"] == n
    assert body["shown_rows"] == 100
    assert body["rows"][0]["id"] == 55_000


def test_rows_session_not_found():
    resp = client.get("/api/data/inconnue/rows")
    assert resp.status_code == 404
