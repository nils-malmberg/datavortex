"""Opérations et transformations de colonnes (Phase 8)."""
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
    rng = np.random.default_rng(55)
    n = 120
    valeurs = rng.normal(50, 12, n)
    valeurs[:10] = np.nan  # une colonne à trous, comme dans la vraie vie
    df = pd.DataFrame({
        "id": np.arange(n),
        "valeur": valeurs,
        "prix": rng.uniform(1, 100, n).round(2),
        "categorie": rng.choice(["a", "b", "c"], n),
        "libelle": [f"item_{i}" for i in range(n)],
    })
    return df, _upload(df)


def _transform(session_id, **kwargs):
    return client.post("/api/columns/transform", json={"session_id": session_id, **kwargs})


def _operation(session_id, **kwargs):
    return client.post("/api/columns/operation", json={"session_id": session_id, **kwargs})


def _columns(session_id):
    return client.get(f"/api/columns/{session_id}").json()


# --- Inventaire --------------------------------------------------------------

def test_column_inventory_describes_each_column(dataset):
    df, session_id = dataset
    body = _columns(session_id)
    assert body["n_columns"] == df.shape[1]
    by_name = {item["name"]: item for item in body["items"]}
    assert by_name["valeur"]["is_numeric"] is True
    assert by_name["valeur"]["missing"] == 10
    assert by_name["categorie"]["unique"] == 3
    assert by_name["libelle"]["is_numeric"] is False
    assert len(by_name["id"]["sample"]) == 3


# --- Opérations de structure -------------------------------------------------

def test_rename_column(dataset):
    _, session_id = dataset
    body = _operation(session_id, op="rename", columns=["valeur"], new_name="mesure").json()
    assert "mesure" in body["columns"] and "valeur" not in body["columns"]


def test_rename_to_existing_name_refused(dataset):
    _, session_id = dataset
    resp = _operation(session_id, op="rename", columns=["valeur"], new_name="prix")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "COLUMN_ALREADY_EXISTS"


def test_duplicate_places_copy_next_to_source(dataset):
    _, session_id = dataset
    body = _operation(session_id, op="duplicate", columns=["prix"]).json()
    columns = body["columns"]
    assert columns[columns.index("prix") + 1] == "prix_copie"
    # Le contenu doit être identique à la source.
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 5}).json()["rows"]
    assert all(row["prix"] == row["prix_copie"] for row in rows)


def test_delete_multiple_columns(dataset):
    _, session_id = dataset
    body = _operation(session_id, op="delete", columns=["libelle", "categorie"]).json()
    assert "libelle" not in body["columns"] and "categorie" not in body["columns"]
    assert body["n_columns"] == 3


def test_cannot_delete_every_column(dataset):
    df, session_id = dataset
    resp = _operation(session_id, op="delete", columns=list(df.columns))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "CANNOT_DELETE_ALL"


def test_reorder_columns(dataset):
    df, session_id = dataset
    new_order = list(reversed([str(c) for c in df.columns]))
    body = _operation(session_id, op="reorder", order=new_order).json()
    assert body["columns"] == new_order


def test_reorder_must_list_exactly_existing_columns(dataset):
    _, session_id = dataset
    resp = _operation(session_id, op="reorder", order=["id", "prix"])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ORDER"


def test_deleting_filtered_column_drops_the_filter(dataset):
    _, session_id = dataset
    client.post("/api/filters/apply", json={
        "session_id": session_id,
        "filter": {"type": "condition", "column": "categorie", "operator": "eq", "value": "a"},
    })
    body = _operation(session_id, op="delete", columns=["categorie"]).json()
    assert body["filter_dropped"] is True
    # La session reste utilisable, sans filtre fantôme sur une colonne disparue.
    assert client.get(f"/api/data/{session_id}/rows").json()["filtered"] is False


def test_filter_survives_an_unrelated_operation(dataset):
    df, session_id = dataset
    filtered = client.post("/api/filters/apply", json={
        "session_id": session_id,
        "filter": {"type": "condition", "column": "categorie", "operator": "eq", "value": "a"},
    }).json()
    _operation(session_id, op="duplicate", columns=["prix"])
    rows = client.get(f"/api/data/{session_id}/rows").json()
    assert rows["filtered"] is True
    assert rows["total_rows"] == filtered["total_rows"]


# --- Découpage en classes ----------------------------------------------------

def test_equal_width_binning_with_missing_values(dataset):
    df, session_id = dataset
    body = _transform(session_id, transform="binning", source="valeur",
                      params={"method": "equal_width", "bins": 4}, new_name="classe").json()
    assert body["created_columns"] == ["classe"]
    # Les valeurs manquantes de la source le restent après découpage.
    assert body["null_count"]["classe"] == 10
    assert "4 classes" in body["description"]


def test_equal_width_bins_match_numpy_edges(dataset):
    df, session_id = dataset
    _transform(session_id, transform="binning", source="prix",
               params={"method": "equal_width", "bins": 4, "as_label": False}, new_name="code")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    edges = np.linspace(df.prix.min(), df.prix.max(), 5)
    expected = pd.cut(df.prix, bins=edges, include_lowest=True).cat.codes
    assert [int(r["code"]) for r in rows] == list(expected)


def test_quantile_binning_makes_balanced_groups(dataset):
    _, session_id = dataset
    _transform(session_id, transform="binning", source="prix",
               params={"method": "quantile", "bins": 4}, new_name="quartile")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    counts = pd.Series([r["quartile"] for r in rows]).value_counts()
    assert counts.max() - counts.min() <= 1


def test_custom_binning_uses_given_edges(dataset):
    _, session_id = dataset
    body = _transform(session_id, transform="binning", source="prix",
                      params={"method": "custom", "edges": [0, 25, 50, 100]}, new_name="tranche").json()
    assert "bornes" in body["description"]
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    assert {r["tranche"] for r in rows} <= {"(-0.001, 25.0]", "(25.0, 50.0]", "(50.0, 100.0]"}


def test_binning_refuses_text_column(dataset):
    _, session_id = dataset
    resp = _transform(session_id, transform="binning", source="libelle", params={"bins": 3})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


def test_binning_refuses_constant_column():
    session_id = _upload(pd.DataFrame({"v": [5.0] * 40, "n": range(40)}))
    resp = _transform(session_id, transform="binning", source="v",
                      params={"method": "equal_width", "bins": 3})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CONSTANT_COLUMN"


def test_binning_rejects_out_of_range_bin_count(dataset):
    _, session_id = dataset
    assert _transform(session_id, transform="binning", source="prix", params={"bins": 1}).status_code == 400
    assert _transform(session_id, transform="binning", source="prix", params={"bins": 500}).status_code == 400


# --- Encodage ----------------------------------------------------------------

def test_label_encoding_is_alphabetical(dataset):
    df, session_id = dataset
    _transform(session_id, transform="encoding", source="categorie",
               params={"method": "label"}, new_name="cat_code")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    mapping = {row["categorie"]: row["cat_code"] for row in rows}
    assert mapping == {"a": 0, "b": 1, "c": 2}


def test_onehot_encoding_creates_one_column_per_level(dataset):
    _, session_id = dataset
    body = _transform(session_id, transform="encoding", source="categorie",
                      params={"method": "onehot"}).json()
    assert set(body["created_columns"]) == {"categorie_a", "categorie_b", "categorie_c"}
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 20}).json()["rows"]
    for row in rows:
        # Exactement une indicatrice active par ligne.
        assert sum(row[c] for c in body["created_columns"]) == 1


def test_onehot_refuses_high_cardinality(dataset):
    _, session_id = dataset
    resp = _transform(session_id, transform="encoding", source="libelle", params={"method": "onehot"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_MANY_LEVELS"


def test_frequency_encoding_matches_value_counts(dataset):
    df, session_id = dataset
    _transform(session_id, transform="encoding", source="categorie",
               params={"method": "frequency"}, new_name="cat_freq")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    counts = df.categorie.value_counts()
    assert all(row["cat_freq"] == counts[row["categorie"]] for row in rows)


# --- Décalage ----------------------------------------------------------------

def test_lag_shifts_values_down(dataset):
    df, session_id = dataset
    body = _transform(session_id, transform="lag", source="prix",
                      params={"periods": 1}, new_name="prix_prec").json()
    assert body["null_count"]["prix_prec"] == 1
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 5}).json()["rows"]
    assert rows[0]["prix_prec"] is None
    assert rows[1]["prix_prec"] == pytest.approx(rows[0]["prix"])


def test_negative_lag_looks_forward(dataset):
    _, session_id = dataset
    _transform(session_id, transform="lag", source="prix", params={"periods": -1}, new_name="prix_suiv")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 5}).json()["rows"]
    assert rows[0]["prix_suiv"] == pytest.approx(rows[1]["prix"])


def test_grouped_lag_does_not_cross_groups(dataset):
    df, session_id = dataset
    body = _transform(session_id, transform="lag", source="prix",
                      params={"periods": 1, "group_by": "categorie"}, new_name="prix_prec").json()
    # Une valeur manquante par groupe, en tête de chaque groupe.
    assert body["null_count"]["prix_prec"] == df.categorie.nunique()
    assert "chaque groupe" in body["description"]


def test_zero_lag_refused(dataset):
    _, session_id = dataset
    resp = _transform(session_id, transform="lag", source="prix", params={"periods": 0})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PERIODS"


# --- Fenêtre glissante -------------------------------------------------------

def test_rolling_mean_matches_pandas(dataset):
    df, session_id = dataset
    _transform(session_id, transform="rolling", source="prix",
               params={"window": 3, "function": "mean"}, new_name="moy3")
    rows = client.get(f"/api/data/{session_id}/rows", params={"limit": 1000}).json()["rows"]
    expected = df.prix.rolling(window=3, min_periods=3).mean()
    for i, row in enumerate(rows):
        if pd.isna(expected.iloc[i]):
            assert row["moy3"] is None
        else:
            assert row["moy3"] == pytest.approx(expected.iloc[i])


def test_centered_rolling_window(dataset):
    _, session_id = dataset
    body = _transform(session_id, transform="rolling", source="prix",
                      params={"window": 5, "function": "mean", "center": True}, new_name="centre").json()
    assert "centrée" in body["description"]


def test_rolling_window_bounds_enforced(dataset):
    _, session_id = dataset
    assert _transform(session_id, transform="rolling", source="prix",
                      params={"window": 1}).status_code == 400
    resp = _transform(session_id, transform="rolling", source="prix", params={"window": 10_000})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "WINDOW_TOO_LARGE"


def test_unknown_rolling_function_lists_available_ones(dataset):
    _, session_id = dataset
    resp = _transform(session_id, transform="rolling", source="prix",
                      params={"window": 3, "function": "moyenne"})
    assert resp.status_code == 400
    assert "median" in resp.json()["error"]["message"]


# --- Garde-fous généraux -----------------------------------------------------

def test_transform_refuses_existing_name_without_replace(dataset):
    _, session_id = dataset
    _transform(session_id, transform="encoding", source="categorie",
               params={"method": "label"}, new_name="code")
    resp = _transform(session_id, transform="encoding", source="categorie",
                      params={"method": "label"}, new_name="code")
    assert resp.status_code == 409
    assert _transform(session_id, transform="encoding", source="categorie",
                      params={"method": "label"}, new_name="code", replace=True).status_code == 200


def test_transformed_column_is_visible_everywhere(dataset):
    _, session_id = dataset
    _transform(session_id, transform="encoding", source="categorie",
               params={"method": "label"}, new_name="cat_code")
    assert "cat_code" in client.get(f"/api/data/{session_id}/preview").json()["columns"]
    assert "cat_code" in client.get(f"/api/stats/{session_id}").json()["columns"]


def test_columns_session_not_found():
    assert client.get("/api/columns/inconnue").status_code == 404
    assert client.post("/api/columns/transform", json={
        "session_id": "inconnue", "transform": "encoding", "source": "a",
    }).status_code == 404
