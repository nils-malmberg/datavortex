"""Statistiques avancées (Phase 8).

Les valeurs attendues sont recalculées directement avec scipy/pandas dans le
test : on vérifie que l'API expose bien le résultat de référence, pas seulement
qu'elle renvoie un code 200.
"""
import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app.main import app

client = TestClient(app)


def _make_dataset() -> pd.DataFrame:
    rng = np.random.default_rng(1234)
    n = 240
    x = rng.normal(50, 10, n)
    return pd.DataFrame({
        # y est fortement corrélée à x, z ne l'est pas du tout.
        "x": x,
        "y": 2.5 * x + rng.normal(0, 5, n),
        "z": rng.normal(0, 1, n),
        "skewed": rng.exponential(3, n),
        "group": rng.choice(["a", "b", "c"], n),
    })


def _upload(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    resp = client.post("/api/upload", files={"file": ("data.csv", buf.getvalue().encode(), "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


@pytest.fixture()
def dataset():
    df = _make_dataset()
    return df, _upload(df)


def test_advanced_stats_structure(dataset):
    _, session_id = dataset
    body = client.get(f"/api/stats/{session_id}/advanced").json()
    assert set(body) >= {"summary", "correlations", "distributions", "missing", "numeric_columns"}
    assert body["numeric_columns"] == ["x", "y", "z", "skewed"]
    assert body["categorical_columns"] == ["group"]


def test_summary_matches_pandas(dataset):
    df, session_id = dataset
    stats = client.get(f"/api/stats/{session_id}/advanced").json()["summary"]["x"]
    col = df["x"]
    n = len(col)
    assert stats["count"] == n
    assert stats["mean"] == pytest.approx(col.mean())
    assert stats["std"] == pytest.approx(col.std())
    assert stats["std_error"] == pytest.approx(col.std() / np.sqrt(n))
    assert stats["cv_percent"] == pytest.approx(col.std() / abs(col.mean()) * 100)
    assert stats["iqr"] == pytest.approx(col.quantile(0.75) - col.quantile(0.25))
    assert stats["mad"] == pytest.approx((col - col.median()).abs().median())


def test_confidence_intervals_match_student(dataset):
    df, session_id = dataset
    stats = client.get(f"/api/stats/{session_id}/advanced").json()["summary"]["x"]
    col = df["x"]
    n = len(col)
    for level, key in ((0.95, "ci95"), (0.99, "ci99")):
        margin = sps.t.ppf(0.5 + level / 2, df=n - 1) * col.std() / np.sqrt(n)
        assert stats[key]["low"] == pytest.approx(col.mean() - margin)
        assert stats[key]["high"] == pytest.approx(col.mean() + margin)
    # Un IC à 99 % est nécessairement plus large qu'un IC à 95 %.
    assert stats["ci99"]["margin"] > stats["ci95"]["margin"]


def test_correlation_matrix_matches_scipy(dataset):
    df, session_id = dataset
    corr = client.get(f"/api/stats/{session_id}/advanced").json()["correlations"]
    cols = corr["columns"]
    i, j = cols.index("x"), cols.index("y")
    expected_r, expected_p = sps.pearsonr(df["x"], df["y"])
    assert corr["matrix"][i][j] == pytest.approx(expected_r)
    assert corr["p_values"][i][j] == pytest.approx(expected_p)
    # La matrice est symétrique et sa diagonale vaut 1.
    assert corr["matrix"][j][i] == pytest.approx(expected_r)
    assert corr["matrix"][i][i] == pytest.approx(1.0)
    # x/y sont liées, x/z ne le sont pas : la p-value doit trancher.
    k = cols.index("z")
    assert corr["p_values"][i][j] < 0.001
    assert corr["p_values"][i][k] > 0.05


def test_correlation_spearman_differs_from_pearson(dataset):
    df, session_id = dataset
    body = client.get(f"/api/stats/{session_id}/advanced", params={"method": "spearman"}).json()
    corr = body["correlations"]
    assert corr["method"] == "spearman"
    cols = corr["columns"]
    i, j = cols.index("x"), cols.index("skewed")
    expected = sps.spearmanr(df["x"], df["skewed"])
    assert corr["matrix"][i][j] == pytest.approx(expected.statistic)


def test_correlation_unknown_method_rejected(dataset):
    _, session_id = dataset
    resp = client.get(f"/api/stats/{session_id}/advanced", params={"method": "cosine"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_CORRELATION_METHOD"


def test_clustered_order_groups_correlated_columns(dataset):
    _, session_id = dataset
    corr = client.get(f"/api/stats/{session_id}/advanced").json()["correlations"]
    order = corr["clustered_order"]
    assert sorted(order) == sorted(corr["columns"])
    # x et y sont quasi colinéaires : le clustering doit les rendre adjacentes.
    assert abs(order.index("x") - order.index("y")) == 1


def test_distribution_detects_normal_and_skewed(dataset):
    df, session_id = dataset
    dist = client.get(f"/api/stats/{session_id}/advanced").json()["distributions"]

    normal = dist["z"]
    assert normal["is_normal"] is True
    assert normal["skewness"] == pytest.approx(sps.skew(df["z"]))
    assert normal["kurtosis"] == pytest.approx(sps.kurtosis(df["z"]))
    assert "symétrique" in normal["skewness_interpretation"]

    skewed = dist["skewed"]
    assert skewed["is_normal"] is False
    assert skewed["skewness"] > 1
    assert "droite" in skewed["skewness_interpretation"]
    # Les données viennent d'une loi exponentielle : elle doit être retenue.
    assert skewed["detected_law"] == "exponential"


def test_shapiro_matches_scipy(dataset):
    df, session_id = dataset
    dist = client.get(f"/api/stats/{session_id}/advanced").json()["distributions"]["z"]
    stat, p = sps.shapiro(df["z"])
    assert dist["normality"]["shapiro"]["statistic"] == pytest.approx(stat)
    assert dist["normality"]["shapiro"]["p_value"] == pytest.approx(p)


def test_no_law_reported_when_none_fits():
    # Mélange de deux gaussiennes très séparées : aucune loi usuelle ne colle.
    rng = np.random.default_rng(7)
    bimodal = np.concatenate([rng.normal(0, 1, 150), rng.normal(30, 1, 150)])
    session_id = _upload(pd.DataFrame({"bimodal": bimodal, "other": rng.normal(0, 1, 300)}))
    dist = client.get(f"/api/stats/{session_id}/advanced").json()["distributions"]["bimodal"]
    assert dist["is_normal"] is False
    assert dist["detected_law"] is None
    assert "Aucune loi usuelle" in dist["fit_message"]


def test_qq_plot_points_are_returned(dataset):
    _, session_id = dataset
    qq = client.get(f"/api/stats/{session_id}/advanced").json()["distributions"]["z"]["qq_plot"]
    assert len(qq["theoretical"]) == len(qq["sample"]) > 0
    # Pour une variable normale, la droite de référence doit être bien ajustée.
    assert qq["r"] > 0.99


def test_missing_analysis_counts_and_patterns():
    df = pd.DataFrame({
        "a": [1.0, 2.0, None, 4.0, None, 6.0],
        "b": [None, 2.0, None, 4.0, 5.0, 6.0],
        "c": [1, 2, 3, 4, 5, 6],
    })
    session_id = _upload(df)
    missing = client.get(f"/api/stats/{session_id}/advanced").json()["missing"]

    assert missing["total_missing"] == 4
    assert missing["complete_rows"] == 3
    assert missing["columns_with_missing"] == 2

    by_col = {c["column"]: c for c in missing["by_column"]}
    assert by_col["a"]["missing_count"] == 2
    assert by_col["c"]["missing_count"] == 0
    assert by_col["c"]["suggestion"]["method"] == "none"

    # Une ligne où a et b manquent simultanément doit ressortir comme pattern.
    patterns = {tuple(p["columns_missing"]): p["count"] for p in missing["patterns"]}
    assert patterns[("a", "b")] == 1
    assert patterns[()] == 3


def test_imputation_suggestions_follow_distribution_shape():
    rng = np.random.default_rng(3)
    n = 200
    symmetric = rng.normal(10, 2, n)
    skewed = rng.exponential(5, n)
    symmetric[:20] = np.nan
    skewed[:20] = np.nan
    df = pd.DataFrame({
        "symmetric": symmetric,
        "skewed": skewed,
        "mostly_empty": [1.0] * 20 + [np.nan] * (n - 20),
        "category": ["a" if i % 2 else "b" for i in range(n - 10)] + [None] * 10,
    })
    session_id = _upload(df)
    by_col = {
        c["column"]: c["suggestion"]
        for c in client.get(f"/api/stats/{session_id}/advanced").json()["missing"]["by_column"]
    }
    assert by_col["symmetric"]["method"] == "mean"
    assert by_col["skewed"]["method"] == "median"
    assert by_col["mostly_empty"]["method"] == "drop_column"
    assert by_col["category"]["method"] == "mode"


@pytest.mark.parametrize("table", ["summary", "correlations", "distributions", "missing"])
@pytest.mark.parametrize("fmt", ["csv", "excel", "latex"])
def test_stats_export_formats(dataset, table, fmt):
    _, session_id = dataset
    resp = client.post("/api/stats/export", json={
        "session_id": session_id, "table": table, "format": fmt, "precision": 3,
    })
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0
    assert "attachment" in resp.headers["content-disposition"]
    if fmt == "csv":
        assert b"Colonne" in resp.content
    elif fmt == "latex":
        assert b"tabular" in resp.content
    else:
        assert resp.content[:2] == b"PK"  # un .xlsx est une archive ZIP


def test_stats_export_rejects_unknown_table(dataset):
    _, session_id = dataset
    resp = client.post("/api/stats/export", json={"session_id": session_id, "table": "bogus", "format": "csv"})
    assert resp.status_code == 422  # rejeté par la validation Pydantic


def test_advanced_stats_session_not_found():
    resp = client.get("/api/stats/inconnue/advanced")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"
