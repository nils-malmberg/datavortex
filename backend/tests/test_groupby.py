"""Agrégations par groupe (Phase 8), confrontées à pandas."""
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
    rng = np.random.default_rng(17)
    n = 300
    df = pd.DataFrame({
        "region": rng.choice(["nord", "sud", "est"], n),
        "produit": rng.choice(["A", "B"], n),
        "ventes": rng.integers(1, 500, n).astype(float),
        "marge": rng.normal(0.2, 0.05, n),
    })
    return df, _upload(df)


def _groupby(session_id, **kwargs):
    return client.post("/api/groupby", json={"session_id": session_id, **kwargs})


def test_single_group_mean_matches_pandas(dataset):
    df, session_id = dataset
    body = _groupby(session_id, group_by=["region"],
                    aggregations=[{"column": "ventes", "func": "mean"}]).json()
    expected = df.groupby("region")["ventes"].mean()
    assert body["group_count"] == expected.size
    for row in body["rows"]:
        assert row["ventes_mean"] == pytest.approx(expected[row["region"]])


def test_multiple_aggregations_and_aliases(dataset):
    df, session_id = dataset
    body = _groupby(session_id, group_by=["region"], aggregations=[
        {"column": "ventes", "func": "sum", "alias": "total"},
        {"column": "ventes", "func": "std"},
        {"column": "marge", "func": "median", "alias": "marge_med"},
        {"column": "produit", "func": "nunique"},
    ]).json()
    assert body["value_columns"] == ["total", "ventes_std", "marge_med", "produit_nunique"]
    grouped = df.groupby("region")
    for row in body["rows"]:
        region = row["region"]
        assert row["total"] == pytest.approx(grouped["ventes"].sum()[region])
        assert row["ventes_std"] == pytest.approx(grouped["ventes"].std()[region])
        assert row["marge_med"] == pytest.approx(grouped["marge"].median()[region])
        assert row["produit_nunique"] == grouped["produit"].nunique()[region]


def test_multiple_group_columns_produce_crossed_groups(dataset):
    df, session_id = dataset
    body = _groupby(session_id, group_by=["region", "produit"],
                    aggregations=[{"column": "ventes", "func": "count", "alias": "n"}]).json()
    expected = df.groupby(["region", "produit"]).size()
    assert body["group_count"] == expected.size
    assert body["group_columns"] == ["region", "produit"]
    for row in body["rows"]:
        assert row["n"] == expected[(row["region"], row["produit"])]


def test_quantile_aggregation_matches_pandas(dataset):
    df, session_id = dataset
    body = _groupby(session_id, group_by=["region"],
                    aggregations=[{"column": "ventes", "func": "quantile", "quantile": 0.9}]).json()
    expected = df.groupby("region")["ventes"].quantile(0.9)
    for row in body["rows"]:
        assert row["ventes_q0.9"] == pytest.approx(expected[row["region"]])


def test_sem_aggregation_matches_pandas(dataset):
    df, session_id = dataset
    body = _groupby(session_id, group_by=["region"],
                    aggregations=[{"column": "marge", "func": "sem"}]).json()
    expected = df.groupby("region")["marge"].sem()
    for row in body["rows"]:
        assert row["marge_sem"] == pytest.approx(expected[row["region"]])


def test_sorting_result_by_aggregate(dataset):
    _, session_id = dataset
    ascending = _groupby(session_id, group_by=["region"],
                         aggregations=[{"column": "ventes", "func": "mean"}],
                         sort_by="ventes_mean", sort_ascending=True).json()
    values = [r["ventes_mean"] for r in ascending["rows"]]
    assert values == sorted(values)
    descending = _groupby(session_id, group_by=["region"],
                          aggregations=[{"column": "ventes", "func": "mean"}],
                          sort_by="ventes_mean", sort_ascending=False).json()
    assert [r["ventes_mean"] for r in descending["rows"]] == sorted(values, reverse=True)


def test_numeric_only_aggregation_rejected_on_text(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=["region"], aggregations=[{"column": "produit", "func": "mean"}])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


def test_count_allowed_on_text_column(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=["region"], aggregations=[{"column": "produit", "func": "count"}])
    assert resp.status_code == 200


def test_duplicate_alias_rejected(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=["region"], aggregations=[
        {"column": "ventes", "func": "mean", "alias": "x"},
        {"column": "marge", "func": "mean", "alias": "x"},
    ])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "DUPLICATE_ALIAS"


def test_missing_group_by_rejected(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=[], aggregations=[{"column": "ventes", "func": "mean"}])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_GROUP_BY"


def test_missing_aggregations_rejected(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=["region"], aggregations=[])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_AGGREGATIONS"


def test_invalid_sort_column_lists_available_columns(dataset):
    _, session_id = dataset
    resp = _groupby(session_id, group_by=["region"],
                    aggregations=[{"column": "ventes", "func": "mean"}], sort_by="inconnue")
    assert resp.status_code == 400
    assert "ventes_mean" in resp.json()["error"]["message"]


def test_too_many_groups_rejected():
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"key": [f"k{i}" for i in range(6000)], "v": rng.normal(0, 1, 6000)})
    session_id = _upload(df)
    resp = _groupby(session_id, group_by=["key"], aggregations=[{"column": "v", "func": "mean"}])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_GROUPS"


def test_result_is_truncated_but_group_count_is_complete(dataset):
    _, session_id = dataset
    body = _groupby(session_id, group_by=["region", "produit"],
                    aggregations=[{"column": "ventes", "func": "mean"}], limit=2).json()
    assert body["shown_rows"] == 2
    assert body["truncated"] is True
    assert body["group_count"] == 6


def test_bar_figure_has_one_trace_per_numeric_aggregate(dataset):
    _, session_id = dataset
    body = _groupby(session_id, group_by=["region"], aggregations=[
        {"column": "ventes", "func": "mean"},
        {"column": "marge", "func": "mean"},
    ]).json()
    assert len(body["figure"]["data"]) == 2


def test_groupby_respects_active_filter(dataset):
    df, session_id = dataset
    client.post("/api/filters/apply", json={
        "session_id": session_id,
        "filter": {"type": "condition", "column": "produit", "operator": "eq", "value": "A"},
    })
    body = _groupby(session_id, group_by=["region"],
                    aggregations=[{"column": "ventes", "func": "count", "alias": "n"}]).json()
    expected = df[df["produit"] == "A"].groupby("region").size()
    for row in body["rows"]:
        assert row["n"] == expected[row["region"]]


@pytest.mark.parametrize("fmt", ["csv", "excel", "latex"])
def test_groupby_export_formats(dataset, fmt):
    _, session_id = dataset
    resp = client.post("/api/groupby/export", json={
        "session_id": session_id, "group_by": ["region"],
        "aggregations": [{"column": "ventes", "func": "mean"}],
        "format": fmt, "precision": 2,
    })
    assert resp.status_code == 200
    assert len(resp.content) > 0


def test_groupby_session_not_found():
    resp = client.post("/api/groupby", json={
        "session_id": "inconnue", "group_by": ["a"], "aggregations": [{"column": "b", "func": "mean"}],
    })
    assert resp.status_code == 404
