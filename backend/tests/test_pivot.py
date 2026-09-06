"""Tableaux croisés dynamiques (Phase 8), confrontés à pandas."""
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
    rng = np.random.default_rng(31)
    n = 400
    df = pd.DataFrame({
        "sexe": rng.choice(["f", "m"], n),
        "classe": rng.choice([1, 2, 3], n),
        "survecu": rng.integers(0, 2, n),
        "prix": rng.uniform(5, 300, n),
        "nom": [f"p{i}" for i in range(n)],
    })
    return df, _upload(df)


def _pivot(session_id, **kwargs):
    return client.post("/api/pivot", json={"session_id": session_id, **kwargs})


def _cell(body, index_col, index_value, column):
    row = next(r for r in body["rows"] if r[index_col] == index_value)
    return row[column]


def test_pivot_mean_matches_pandas(dataset):
    df, session_id = dataset
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="survecu", aggfunc="mean").json()
    expected = pd.pivot_table(df, index="sexe", columns="classe", values="survecu", aggfunc="mean")
    for sexe in expected.index:
        for classe in expected.columns:
            assert _cell(body, "sexe", sexe, str(classe)) == pytest.approx(expected.loc[sexe, classe])


def test_pivot_with_margins_matches_pandas(dataset):
    df, session_id = dataset
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="prix",
                  aggfunc="mean", margins=True).json()
    expected = pd.pivot_table(df, index="sexe", columns="classe", values="prix",
                              aggfunc="mean", margins=True, margins_name="Total")
    assert "Total" in body["columns"]
    assert _cell(body, "sexe", "f", "Total") == pytest.approx(expected.loc["f", "Total"])
    assert _cell(body, "sexe", "Total", "Total") == pytest.approx(expected.loc["Total", "Total"])


def test_pivot_without_columns_produces_single_series(dataset):
    df, session_id = dataset
    body = _pivot(session_id, index=["sexe"], values="prix", aggfunc="mean").json()
    expected = df.groupby("sexe")["prix"].mean()
    assert body["n_value_columns"] == 1
    value_col = body["value_columns"][0]
    for sexe in expected.index:
        assert _cell(body, "sexe", sexe, value_col) == pytest.approx(expected[sexe])


def test_percentage_of_total_sums_to_100(dataset):
    _, session_id = dataset
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="nom",
                  aggfunc="count", margins=True, percentage="total").json()
    # La cellule d'intersection des deux marges vaut 100 % du tableau.
    assert _cell(body, "sexe", "Total", "Total") == pytest.approx(100.0)
    data_cells = [
        row[col] for row in body["rows"] if row["sexe"] != "Total"
        for col in body["value_columns"] if col != "Total"
    ]
    assert sum(v for v in data_cells if v is not None) == pytest.approx(100.0)


def test_percentage_by_row_each_row_sums_to_100(dataset):
    _, session_id = dataset
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="nom",
                  aggfunc="count", margins=True, percentage="row").json()
    data_columns = [c for c in body["value_columns"] if c != "Total"]
    for row in body["rows"]:
        assert sum(row[c] for c in data_columns if row[c] is not None) == pytest.approx(100.0)
        assert row["Total"] == pytest.approx(100.0)


def test_percentage_by_column_each_column_sums_to_100(dataset):
    _, session_id = dataset
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="nom",
                  aggfunc="count", margins=True, percentage="column").json()
    data_rows = [r for r in body["rows"] if r["sexe"] != "Total"]
    for col in body["value_columns"]:
        assert sum(r[col] for r in data_rows if r[col] is not None) == pytest.approx(100.0)


def test_multiple_index_and_column_fields(dataset):
    df, session_id = dataset
    body = _pivot(session_id, index=["sexe", "survecu"], columns=["classe"],
                  values="prix", aggfunc="mean").json()
    assert body["index_columns"] == ["sexe", "survecu"]
    expected = pd.pivot_table(df, index=["sexe", "survecu"], columns="classe", values="prix", aggfunc="mean")
    assert body["n_rows"] == expected.shape[0]


def test_missing_modality_is_labelled_not_nan():
    df = pd.DataFrame({
        "groupe": ["a", "b", None, "a", "b", None],
        "canal": ["x", "y", "x", "y", "x", "y"],
        "valeur": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    })
    session_id = _upload(df)
    body = _pivot(session_id, index=["groupe"], columns=["canal"], values="valeur", aggfunc="mean").json()
    labels = [r["groupe"] for r in body["rows"]]
    assert "(vide)" in labels
    assert "nan" not in labels


def test_empty_heatmap_cells_render_blank():
    df = pd.DataFrame({
        "a": ["x", "x", "y"], "b": ["p", "p", "q"], "v": [1.0, 2.0, 3.0],
    })
    session_id = _upload(df)
    body = _pivot(session_id, index=["a"], columns=["b"], values="v", aggfunc="mean").json()
    annotations = body["figure"]["data"][0]["text"]
    flat = [cell for row in annotations for cell in row]
    # Les combinaisons absentes sont vides, jamais « 0 ».
    assert "" in flat
    assert "0" not in flat


def test_overlapping_index_and_columns_rejected(dataset):
    _, session_id = dataset
    resp = _pivot(session_id, index=["sexe"], columns=["sexe"], values="prix")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "OVERLAPPING_FIELDS"


def test_numeric_aggfunc_rejected_on_text_values(dataset):
    _, session_id = dataset
    resp = _pivot(session_id, index=["sexe"], columns=["classe"], values="nom", aggfunc="mean")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


def test_count_allowed_on_text_values(dataset):
    _, session_id = dataset
    assert _pivot(session_id, index=["sexe"], columns=["classe"], values="nom", aggfunc="count").status_code == 200


def test_missing_index_rejected(dataset):
    _, session_id = dataset
    resp = _pivot(session_id, index=[], columns=["classe"], values="prix")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_INDEX"


def test_missing_values_rejected(dataset):
    _, session_id = dataset
    resp = _pivot(session_id, index=["sexe"], columns=["classe"])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_VALUES"


def test_too_many_pivot_columns_rejected():
    rng = np.random.default_rng(8)
    df = pd.DataFrame({
        "ligne": rng.choice(list("ab"), 600),
        "colonne": [f"c{i}" for i in range(600)],
        "v": rng.normal(0, 1, 600),
    })
    session_id = _upload(df)
    resp = _pivot(session_id, index=["ligne"], columns=["colonne"], values="v")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_PIVOT_COLUMNS"


def test_heatmap_is_truncated_but_table_is_complete():
    rng = np.random.default_rng(12)
    n = 400
    df = pd.DataFrame({
        "cle": [f"k{i}" for i in range(n)],
        "canal": rng.choice(["x", "y"], n),
        "v": rng.normal(0, 1, n),
    })
    session_id = _upload(df)
    body = _pivot(session_id, index=["cle"], columns=["canal"], values="v", aggfunc="mean").json()
    assert body["n_rows"] == n
    assert body["heatmap_truncated"] is True
    assert len(body["figure"]["data"][0]["y"]) == 60


def test_pivot_respects_active_filter(dataset):
    df, session_id = dataset
    client.post("/api/filters/apply", json={
        "session_id": session_id,
        "filter": {"type": "condition", "column": "sexe", "operator": "eq", "value": "f"},
    })
    body = _pivot(session_id, index=["sexe"], columns=["classe"], values="prix", aggfunc="mean").json()
    assert [r["sexe"] for r in body["rows"]] == ["f"]
    expected = df[df["sexe"] == "f"].groupby("classe")["prix"].mean()
    assert _cell(body, "sexe", "f", "1") == pytest.approx(expected[1])


@pytest.mark.parametrize("fmt", ["csv", "excel", "latex"])
def test_pivot_export_formats(dataset, fmt):
    _, session_id = dataset
    resp = client.post("/api/pivot/export", json={
        "session_id": session_id, "index": ["sexe"], "columns": ["classe"],
        "values": "prix", "aggfunc": "mean", "format": fmt,
    })
    assert resp.status_code == 200
    assert len(resp.content) > 0


def test_pivot_session_not_found():
    resp = client.post("/api/pivot", json={"session_id": "inconnue", "index": ["a"], "values": "b"})
    assert resp.status_code == 404
