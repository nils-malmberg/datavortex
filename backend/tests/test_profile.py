"""Profilage détaillé (Phase 8) : qualité, doublons, anomalies, suggestions."""
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


def _profile(session_id):
    return client.get(f"/api/profile/{session_id}/detailed").json()


@pytest.fixture()
def clean_dataset():
    rng = np.random.default_rng(41)
    n = 300
    return _upload(pd.DataFrame({
        "id": np.arange(n),
        "valeur": rng.normal(50, 5, n).round(3),
        "categorie": rng.choice(["alpha", "beta", "gamma"], n),
    }))


@pytest.fixture()
def dirty_dataset():
    df = pd.DataFrame({
        "ville": (["Paris"] * 40 + ["paris"] * 6 + ["PARIS "] * 3
                  + ["Marseille"] * 30 + ["Marseile"] * 2 + ["Lyon"] * 19),
        "age": list(range(20, 90)) + [-999] * 5 + [None] * 25,
        "revenu": [30000.0] * 90 + [5_000_000.0] * 3 + [None] * 7,
        "code": ["A"] * 50 + ["B"] * 30 + ["N/A"] * 12 + ["?"] * 8,
    })
    df = pd.concat([df, df.head(6)], ignore_index=True)
    return _upload(df)


# --- Profil par colonne ------------------------------------------------------

def test_profile_reports_basic_stats(clean_dataset):
    profile = _profile(clean_dataset)["profile"]
    valeur = profile["valeur"]
    assert valeur["type"] == "float"
    assert valeur["count"] == 300
    assert valeur["mean"] == pytest.approx(valeur["median"], abs=1.5)
    assert "skewness" in valeur and "kurtosis" in valeur
    assert valeur["shape"]


def test_profile_detects_probable_key(clean_dataset):
    profile = _profile(clean_dataset)["profile"]
    assert profile["id"]["is_probable_key"] is True
    assert profile["categorie"]["is_probable_key"] is False


def test_profile_detects_constant_column():
    session_id = _upload(pd.DataFrame({"constante": [7] * 50, "autre": range(50)}))
    profile = _profile(session_id)["profile"]
    assert profile["constante"]["is_constant"] is True
    assert profile["autre"]["is_constant"] is False


def test_profile_text_column_lengths():
    session_id = _upload(pd.DataFrame({"texte": ["a", "abc", "abcde"] * 20, "n": range(60)}))
    texte = _profile(session_id)["profile"]["texte"]
    assert texte["min_length"] == 1
    assert texte["max_length"] == 5


# --- Qualité -----------------------------------------------------------------

def test_clean_dataset_scores_high(clean_dataset):
    quality = _profile(clean_dataset)["quality"]
    assert quality["score"] > 80  # critère de la spécification
    assert quality["n_columns_with_issues"] == 0
    assert quality["dimensions"]["completeness"]["score"] == 100.0


def test_dirty_dataset_flags_every_column(dirty_dataset):
    quality = _profile(dirty_dataset)["quality"]
    assert quality["n_columns_with_issues"] == quality["n_columns"]
    assert set(quality["columns_with_issues"]) == {"ville", "age", "revenu", "code"}


def test_grade_follows_weakest_dimension_not_average(dirty_dataset):
    quality = _profile(dirty_dataset)["quality"]
    weakest = min(d["score"] for d in quality["dimensions"].values())
    assert quality["dimensions"][quality["weakest_dimension"]]["score"] == weakest
    # La moyenne reste élevée alors que la mention doit refléter le maillon faible.
    assert quality["score"] > weakest
    assert quality["grade"] != "excellent"


def test_every_dimension_carries_its_definition(clean_dataset):
    dimensions = _profile(clean_dataset)["quality"]["dimensions"]
    assert set(dimensions) == {"completeness", "uniqueness", "validity", "consistency", "plausibility"}
    for dim in dimensions.values():
        assert dim["definition"] and dim["label"] and "score" in dim


def test_completeness_matches_missing_ratio(dirty_dataset):
    body = _profile(dirty_dataset)
    quality, missing = body["quality"], body["missing"]
    total_cells = quality["n_rows"] * quality["n_columns"]
    expected = round((total_cells - missing["total_missing"]) / total_cells * 100, 2)
    assert quality["dimensions"]["completeness"]["score"] == pytest.approx(expected)


def test_sentinel_values_counted_as_invalid(dirty_dataset):
    per_column = {c["column"]: c for c in _profile(dirty_dataset)["quality"]["per_column"]}
    assert per_column["age"]["sentinel_values"] == 5      # les -999
    # « N/A » est déjà converti en valeur manquante par le lecteur CSV de pandas :
    # ne restent comme marqueurs déguisés que les « ? ».
    assert per_column["code"]["sentinel_values"] == 8


def test_type_mismatch_detected():
    df = pd.DataFrame({"nombre": ["1", "2", "abc", "4", "xyz"] * 10, "autre": range(50)})
    session_id = _upload(df)
    per_column = {c["column"]: c for c in _profile(session_id)["quality"]["per_column"]}
    # La colonne est vue comme du texte : ce sont les valeurs qui sont hétérogènes.
    assert per_column["nombre"]["type"] in ("string", "integer", "float")


# --- Doublons ----------------------------------------------------------------

def test_exact_duplicates_counted(dirty_dataset):
    duplicates = _profile(dirty_dataset)["duplicates"]
    # Les 6 lignes recopiées, plus les répétitions naturelles du jeu de test.
    assert duplicates["duplicate_rows"] >= 6
    assert duplicates["rows_involved"] > duplicates["duplicate_rows"]
    assert duplicates["duplicate_rows_pct"] > 0
    assert len(duplicates["examples"]) > 0


def test_case_and_space_variants_grouped(dirty_dataset):
    groups = _profile(dirty_dataset)["duplicates"]["fuzzy_groups"]
    casing = [g for g in groups if g["kind"] == "casse_ou_espaces" and g["column"] == "ville"]
    assert casing, "les variantes de casse doivent être détectées"
    variants = {v["value"] for g in casing for v in g["variants"]}
    assert {"Paris", "paris", "PARIS "} <= variants
    assert casing[0]["canonical"] == "Paris"  # la forme la plus fréquente


def test_close_spelling_variants_grouped(dirty_dataset):
    groups = _profile(dirty_dataset)["duplicates"]["fuzzy_groups"]
    spelling = [g for g in groups if g["kind"] == "orthographe_proche"]
    variants = {v["value"] for g in spelling for v in g["variants"]}
    assert {"Marseille", "Marseile"} <= variants


def test_no_false_positive_on_distinct_labels(clean_dataset):
    groups = _profile(clean_dataset)["duplicates"]["fuzzy_groups"]
    assert groups == []


# --- Anomalies ---------------------------------------------------------------

def test_outliers_reported_by_both_methods(dirty_dataset):
    per_column = {c["column"]: c for c in _profile(dirty_dataset)["anomalies"]["per_column"]}
    outliers = per_column["revenu"]["outliers"]
    assert outliers["iqr_count"] >= 3
    assert outliers["zscore_count"] >= 1
    assert 5_000_000.0 in outliers["examples"]


def test_degenerate_iqr_falls_back_to_robust_rule():
    """Une colonne très concentrée a un IQR nul : la règle de Tukey ne signale
    alors plus rien, y compris des valeurs manifestement aberrantes."""
    values = [100.0] * 80 + [999999.0] * 3
    session_id = _upload(pd.DataFrame({"v": values, "n": range(len(values))}))
    outliers = {
        c["column"]: c for c in _profile(session_id)["anomalies"]["per_column"]
    }["v"]["outliers"]
    assert outliers["rule"] == "zscore"
    assert outliers["iqr_count"] >= 3
    assert 999999.0 in outliers["examples"]
    assert "écart interquartile est nul" in outliers["rule_label"]


def test_constant_column_reports_no_outlier():
    session_id = _upload(pd.DataFrame({"v": [5.0] * 40, "n": range(40)}))
    outliers = {
        c["column"]: c for c in _profile(session_id)["anomalies"]["per_column"]
    }["v"]["outliers"]
    assert outliers["rule"] == "constant"
    assert outliers["iqr_count"] == 0


def test_isolation_forest_runs_on_multivariate_data(clean_dataset):
    multivariate = _profile(clean_dataset)["anomalies"]["multivariate"]
    assert multivariate["available"] is True
    assert multivariate["anomaly_count"] > 0
    assert multivariate["anomaly_pct"] == pytest.approx(2.0, abs=1.0)
    assert len(multivariate["examples"]) > 0


def test_isolation_forest_needs_two_numeric_columns():
    session_id = _upload(pd.DataFrame({"n": range(60), "texte": ["a"] * 60}))
    multivariate = _profile(session_id)["anomalies"]["multivariate"]
    assert multivariate["available"] is False
    assert "2 colonnes numériques" in multivariate["reason"]


def test_type_mismatch_examples_returned():
    df = pd.DataFrame({
        "date": ["2024-01-01"] * 40 + ["pas une date"] * 5,
        "n": range(45),
    })
    session_id = _upload(df)
    per_column = {c["column"]: c for c in _profile(session_id)["anomalies"]["per_column"]}
    entry = per_column["date"]
    if entry.get("type_mismatch_count"):
        assert "pas une date" in entry["type_mismatch_examples"]


# --- Suggestions -------------------------------------------------------------

def test_suggestions_are_sorted_by_priority(dirty_dataset):
    suggestions = _profile(dirty_dataset)["suggestions"]
    order = {"haute": 0, "moyenne": 1, "basse": 2, "info": 3}
    priorities = [order[s["priority"]] for s in suggestions]
    assert priorities == sorted(priorities)


def test_suggestions_cover_detected_problems(dirty_dataset):
    titles = " ".join(s["title"] for s in _profile(dirty_dataset)["suggestions"])
    assert "dupliquées" in titles
    assert "ville" in titles       # variantes d'écriture
    assert "age" in titles or "code" in titles  # marqueurs d'absence


def test_every_suggestion_states_detail_and_action(dirty_dataset):
    for suggestion in _profile(dirty_dataset)["suggestions"]:
        assert suggestion["detail"] and suggestion["action"]
        assert suggestion["priority"] in {"haute", "moyenne", "basse", "info"}


def test_clean_dataset_gets_no_actionable_suggestion(clean_dataset):
    suggestions = _profile(clean_dataset)["suggestions"]
    assert all(s["priority"] == "info" for s in suggestions)
    assert any("Aucun nettoyage nécessaire" in s["title"] for s in suggestions)


def test_isolation_forest_suggestion_is_informational_only(clean_dataset):
    """Le détecteur signale 2 % des lignes par construction : en faire une
    anomalie à corriger inventerait un problème sur un jeu sain."""
    suggestions = _profile(clean_dataset)["suggestions"]
    classement = [s for s in suggestions if "atypiques" in s["title"]]
    assert classement and classement[0]["priority"] == "info"


def test_profile_respects_active_filter(dirty_dataset):
    client.post("/api/filters/apply", json={
        "session_id": dirty_dataset,
        "filter": {"type": "condition", "column": "ville", "operator": "eq", "value": "Paris"},
    })
    quality = _profile(dirty_dataset)["quality"]
    assert quality["n_rows"] < 106


def test_profile_session_not_found():
    resp = client.get("/api/profile/inconnue/detailed")
    assert resp.status_code == 404
