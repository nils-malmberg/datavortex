"""Filtres avancés (Phase 8) : nouveaux opérateurs, inversion et indicateurs."""
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
    rng = np.random.default_rng(21)
    values = rng.normal(50, 5, 200)
    # Deux valeurs franchement aberrantes, détectables par IQR comme par z-score.
    values[0], values[1] = 200.0, -100.0
    df = pd.DataFrame({
        "value": values,
        "score": rng.integers(0, 100, 200),
        "name": [f"item_{i:03d}" for i in range(200)],
        "group": rng.choice(["alpha", "beta", "gamma"], 200),
    })
    return df, _upload(df)


def _apply(session_id, **kwargs):
    return client.post("/api/filters/apply", json={"session_id": session_id, **kwargs})


def _condition(column, operator, value=None):
    return {"type": "condition", "column": column, "operator": operator, "value": value}


# --- Nouveaux opérateurs ----------------------------------------------------

def test_top_n_keeps_exactly_n_largest(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter=_condition("value", "top_n", 10), preview_mode="kept").json()
    assert body["total_rows"] == 10
    kept = sorted(row["value"] for row in body["rows"])
    # Comparaison à la précision du CSV : l'aller-retour texte perd les derniers bits.
    assert kept == pytest.approx(sorted(df["value"].nlargest(10)))


def test_bottom_n_keeps_exactly_n_smallest(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter=_condition("value", "bottom_n", 5), preview_mode="kept").json()
    assert body["total_rows"] == 5
    kept = sorted(row["value"] for row in body["rows"])
    assert kept == pytest.approx(sorted(df["value"].nsmallest(5)))


def test_top_n_handles_ties_without_overshooting():
    df = pd.DataFrame({"v": [5, 5, 5, 5, 1, 2], "label": list("abcdef")})
    session_id = _upload(df)
    body = _apply(session_id, filter=_condition("v", "top_n", 3)).json()
    assert body["total_rows"] == 3


def test_outlier_iqr_matches_tukey_rule(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter=_condition("value", "outlier_iqr")).json()
    q1, q3 = df["value"].quantile(0.25), df["value"].quantile(0.75)
    iqr = q3 - q1
    expected = ((df["value"] < q1 - 1.5 * iqr) | (df["value"] > q3 + 1.5 * iqr)).sum()
    assert body["total_rows"] == int(expected)
    assert body["total_rows"] >= 2  # les deux valeurs aberrantes injectées


def test_not_outlier_iqr_is_the_complement(dataset):
    _, session_id = dataset
    outliers = _apply(session_id, filter=_condition("value", "outlier_iqr")).json()
    clean = _apply(session_id, filter=_condition("value", "not_outlier_iqr")).json()
    assert outliers["total_rows"] + clean["total_rows"] == outliers["total_rows_unfiltered"]


def test_outlier_zscore_threshold_is_configurable(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter=_condition("value", "outlier_zscore", 3)).json()
    z = ((df["value"] - df["value"].mean()).abs() / df["value"].std())
    assert body["total_rows"] == int((z > 3).sum())
    # Un seuil plus permissif retient au moins autant de lignes.
    loose = _apply(session_id, filter=_condition("value", "outlier_zscore", 1.5)).json()
    assert loose["total_rows"] >= body["total_rows"]


def test_constant_column_has_no_zscore_outlier():
    session_id = _upload(pd.DataFrame({"v": [7.0] * 20, "label": list("abcdefghij") * 2}))
    body = _apply(session_id, filter=_condition("v", "outlier_zscore", 3)).json()
    assert body["total_rows"] == 0


def test_column_wide_operator_rejects_text_column(dataset):
    _, session_id = dataset
    resp = _apply(session_id, filter=_condition("name", "top_n", 5))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


def test_top_n_rejects_non_positive_count(dataset):
    _, session_id = dataset
    resp = _apply(session_id, filter=_condition("value", "top_n", 0))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_FILTER_VALUE"


def test_regex_operator_still_works(dataset):
    _, session_id = dataset
    body = _apply(session_id, filter=_condition("name", "regex", r"^item_0[0-4]\d$")).json()
    assert body["total_rows"] == 50


# --- Inversion et indicateurs ------------------------------------------------

def test_invert_returns_complement(dataset):
    _, session_id = dataset
    normal = _apply(session_id, filter=_condition("group", "eq", "alpha")).json()
    inverted = _apply(session_id, filter=_condition("group", "eq", "alpha"), invert=True).json()
    assert normal["total_rows"] + inverted["total_rows"] == normal["total_rows_unfiltered"]
    assert inverted["inverted"] is True


def test_insights_report_percentages_and_columns(dataset):
    _, session_id = dataset
    body = _apply(session_id, filter={
        "type": "group", "logic": "AND", "conditions": [
            _condition("value", "gt", 45),
            _condition("group", "eq", "alpha"),
        ],
    }).json()
    assert body["kept_pct"] + body["removed_pct"] == pytest.approx(100.0, abs=0.02)
    assert body["total_rows"] + body["removed_rows"] == body["total_rows_unfiltered"]
    assert body["columns_affected"] == ["group", "value"]
    assert body["n_columns_affected"] == 2


def test_per_condition_contribution_is_independent(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter={
        "type": "group", "logic": "AND", "conditions": [
            _condition("value", "gt", 45),
            _condition("group", "eq", "alpha"),
        ],
    }).json()
    contributions = {c["label"]: c["matched_rows"] for c in body["per_condition"]}
    assert contributions["value gt 45"] == int((df["value"] > 45).sum())
    assert contributions["group eq alpha"] == int((df["group"] == "alpha").sum())
    # Le total combiné en ET est au plus le minimum des deux.
    assert body["total_rows"] <= min(contributions.values())


def test_nested_groups_combine_correctly(dataset):
    df, session_id = dataset
    body = _apply(session_id, filter={
        "type": "group", "logic": "AND", "conditions": [
            _condition("value", "gt", 40),
            {"type": "group", "logic": "OR", "conditions": [
                _condition("group", "eq", "alpha"),
                _condition("group", "eq", "beta"),
            ]},
        ],
    }).json()
    expected = ((df["value"] > 40) & df["group"].isin(["alpha", "beta"])).sum()
    assert body["total_rows"] == int(expected)


def test_preview_all_flags_each_row(dataset):
    _, session_id = dataset
    body = _apply(session_id, filter=_condition("group", "eq", "alpha"),
                  preview_mode="all", preview_rows=25).json()
    assert len(body["rows"]) == 25
    assert len(body["row_matches"]) == 25
    assert all(isinstance(flag, bool) for flag in body["row_matches"])
    # Chaque marqueur doit correspondre à la ligne affichée.
    for row, matched in zip(body["rows"], body["row_matches"]):
        assert (row["group"] == "alpha") == matched


def test_preview_removed_shows_only_excluded_rows(dataset):
    _, session_id = dataset
    body = _apply(session_id, filter=_condition("group", "eq", "alpha"), preview_mode="removed").json()
    assert body["row_matches"] is None
    assert all(row["group"] != "alpha" for row in body["rows"])


def test_null_filter_resets_selection(dataset):
    _, session_id = dataset
    _apply(session_id, filter=_condition("group", "eq", "alpha"))
    body = _apply(session_id, filter=None).json()
    assert body["filtered"] is False
    assert body["total_rows"] == body["total_rows_unfiltered"]


def test_filter_result_is_visible_to_other_endpoints(dataset):
    _, session_id = dataset
    body = _apply(session_id, filter=_condition("group", "eq", "alpha")).json()
    stats = client.get(f"/api/stats/{session_id}").json()
    assert stats["n_rows"] == body["total_rows"]
    assert stats["filtered"] is True


def test_advanced_filter_session_not_found():
    resp = client.post("/api/filters/apply", json={"session_id": "inconnue", "filter": None})
    assert resp.status_code == 404
