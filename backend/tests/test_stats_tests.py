"""Tests statistiques (Phase 8).

Chaque résultat est confronté à un appel scipy direct sur les mêmes données :
le test échoue si l'API s'écarte de la référence, pas seulement si elle plante.
"""
import io
import math

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

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
    rng = np.random.default_rng(101)
    n = 60
    df = pd.DataFrame({
        "groupe": ["a"] * n + ["b"] * n + ["c"] * n,
        "bloc": (["x"] * (n // 2) + ["y"] * (n // 2)) * 3,
        "mesure": np.concatenate([
            rng.normal(10, 2, n), rng.normal(13, 2, n), rng.normal(16, 2, n),
        ]),
        "avant": rng.normal(50, 5, 3 * n),
        "apres": rng.normal(53, 5, 3 * n),
        "correle": np.concatenate([rng.normal(10, 2, n), rng.normal(13, 2, n), rng.normal(16, 2, n)]) * 2.5,
    })
    return df, _upload(df)


def _run(session_id, **kwargs):
    return client.post("/api/stats/hypothesis_test", json={"session_id": session_id, **kwargs})


# --- Comparaisons de deux échantillons --------------------------------------

def test_welch_ttest_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                group_column="groupe", group_a="a", group_b="b").json()
    a = df[df.groupe == "a"].mesure.to_numpy()
    b = df[df.groupe == "b"].mesure.to_numpy()
    statistic, p_value = sps.ttest_ind(a, b, equal_var=False)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert body["test_name"] == "Test t de Welch"


def test_student_ttest_when_equal_variance_assumed(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                group_column="groupe", group_a="a", group_b="b", equal_variance=True).json()
    a = df[df.groupe == "a"].mesure.to_numpy()
    b = df[df.groupe == "b"].mesure.to_numpy()
    assert body["test_statistic"] == pytest.approx(sps.ttest_ind(a, b, equal_var=True)[0])
    assert body["test_name"] == "Test t de Student"


def test_cohens_d_matches_formula(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                group_column="groupe", group_a="a", group_b="b").json()
    a = df[df.groupe == "a"].mesure.to_numpy()
    b = df[df.groupe == "b"].mesure.to_numpy()
    n1, n2 = a.size, b.size
    pooled = math.sqrt(((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2))
    assert body["effect_size"]["value"] == pytest.approx((a.mean() - b.mean()) / pooled)
    # La correction de Hedges rapproche l'estimation de zéro.
    assert abs(body["effect_size"]["corrected_value"]) < abs(body["effect_size"]["value"])


def test_mannwhitney_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="mannwhitney", column="mesure",
                group_column="groupe", group_a="a", group_b="b").json()
    a = df[df.groupe == "a"].mesure.to_numpy()
    b = df[df.groupe == "b"].mesure.to_numpy()
    statistic, p_value = sps.mannwhitneyu(a, b)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert body["effect_size"]["value"] == pytest.approx(2 * statistic / (a.size * b.size) - 1)


def test_paired_ttest_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="ttest_rel",
                column="avant", column_b="apres").json()
    statistic, p_value = sps.ttest_rel(df.avant, df.apres)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert body["n_pairs"] == len(df)


def test_wilcoxon_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="wilcoxon",
                column="avant", column_b="apres").json()
    statistic, p_value = sps.wilcoxon(df.avant, df.apres)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)


def test_one_sample_ttest_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="hypothesis", test="ttest_1samp",
                column="mesure", popmean=12.0).json()
    statistic, p_value = sps.ttest_1samp(df.mesure, 12.0)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)


def test_one_sided_alternative_halves_the_p_value(dataset):
    _, session_id = dataset
    two_sided = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                     group_column="groupe", group_a="a", group_b="b").json()
    one_sided = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                     group_column="groupe", group_a="a", group_b="b", alternative="less").json()
    assert one_sided["p_value"] == pytest.approx(two_sided["p_value"] / 2)


def test_decision_warns_that_non_significant_is_not_proof(dataset):
    rng = np.random.default_rng(5)
    df = pd.DataFrame({"g": ["a"] * 30 + ["b"] * 30, "v": rng.normal(0, 1, 60)})
    session_id = _upload(df)
    body = _run(session_id, family="hypothesis", test="ttest_ind", column="v",
                group_column="g", group_a="a", group_b="b").json()
    assert body["decision"]["significant"] is False
    assert "n'est pas démontrer l'absence d'effet" in body["decision"]["text"]


def test_ambiguous_groups_are_refused(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="hypothesis", test="ttest_ind",
                column="mesure", group_column="groupe")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "AMBIGUOUS_GROUPS"


def test_unknown_group_is_refused(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="hypothesis", test="ttest_ind", column="mesure",
                group_column="groupe", group_a="a", group_b="inexistant")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "GROUP_NOT_FOUND"


def test_text_column_refused_for_numeric_test(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="hypothesis", test="ttest_ind", column="groupe",
                group_column="bloc", group_a="x", group_b="y")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


# --- ANOVA -------------------------------------------------------------------

def test_one_way_anova_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="anova", test="one_way",
                column="mesure", factor_a="groupe").json()
    samples = [g.mesure.to_numpy() for _, g in df.groupby("groupe")]
    statistic, p_value = sps.f_oneway(*samples)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert body["degrees_of_freedom"] == [2, len(df) - 3]


def test_anova_sums_of_squares_decompose_total(dataset):
    df, session_id = dataset
    body = _run(session_id, family="anova", test="one_way",
                column="mesure", factor_a="groupe").json()
    rows = {r["source"]: r for r in body["table"]}
    y = df.mesure.to_numpy()
    ss_total = float(((y - y.mean()) ** 2).sum())
    assert rows["groupe"]["ss"] + rows["Résiduelle"]["ss"] == pytest.approx(ss_total)


def test_eta_squared_and_omega_squared(dataset):
    df, session_id = dataset
    body = _run(session_id, family="anova", test="one_way",
                column="mesure", factor_a="groupe").json()
    rows = {r["source"]: r for r in body["table"]}
    ss_total = rows["groupe"]["ss"] + rows["Résiduelle"]["ss"]
    assert body["effect_size"]["value"] == pytest.approx(rows["groupe"]["ss"] / ss_total)
    # ω² corrige à la baisse le biais optimiste de η².
    assert body["effect_size"]["corrected_value"] < body["effect_size"]["value"]


def test_levene_homogeneity_reported(dataset):
    df, session_id = dataset
    body = _run(session_id, family="anova", test="one_way",
                column="mesure", factor_a="groupe").json()
    samples = [g.mesure.to_numpy() for _, g in df.groupby("groupe")]
    assert body["homogeneity"]["p_value"] == pytest.approx(sps.levene(*samples, center="median")[1])


def test_tukey_post_hoc_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="anova", test="one_way", column="mesure",
                factor_a="groupe", post_hoc="tukey").json()
    samples = [g.mesure.to_numpy() for _, g in df.groupby("groupe")]
    reference = sps.tukey_hsd(*samples)
    interval = reference.confidence_interval(0.95)
    comparisons = {(c["group_a"], c["group_b"]): c for c in body["post_hoc"]["comparisons"]}
    labels = sorted(df.groupe.unique())
    for i in range(3):
        for j in range(i + 1, 3):
            comparison = comparisons[(labels[i], labels[j])]
            assert comparison["p_value"] == pytest.approx(reference.pvalue[i, j])
            assert comparison["ci_low"] == pytest.approx(interval.low[i, j])


def test_bonferroni_post_hoc_adjusts_p_values(dataset):
    _, session_id = dataset
    body = _run(session_id, family="anova", test="one_way", column="mesure",
                factor_a="groupe", post_hoc="bonferroni").json()
    for comparison in body["post_hoc"]["comparisons"]:
        expected = min(1.0, comparison["raw_p_value"] * 3)
        assert comparison["p_value"] == pytest.approx(expected)


def test_post_hoc_can_be_disabled(dataset):
    _, session_id = dataset
    body = _run(session_id, family="anova", test="one_way", column="mesure",
                factor_a="groupe", post_hoc="none").json()
    assert body["post_hoc"] is None


def test_two_way_anova_matches_classical_decomposition():
    """Sur un plan équilibré, les sommes de carrés de type II coïncident avec
    la décomposition classique — ce qui valide l'implémentation."""
    rng = np.random.default_rng(77)
    rows = []
    for a, effect_a in [("A1", 0.0), ("A2", 3.0)]:
        for b, effect_b in [("B1", 0.0), ("B2", 2.0), ("B3", 5.0)]:
            interaction = 1.5 if (a == "A2" and b == "B3") else 0.0
            for _ in range(12):
                rows.append({"fa": a, "fb": b,
                             "y": 10 + effect_a + effect_b + interaction + rng.normal(0, 1.2)})
    df = pd.DataFrame(rows)
    session_id = _upload(df)
    body = _run(session_id, family="anova", test="two_way",
                column="y", factor_a="fa", factor_b="fb").json()

    y = df.y.to_numpy()
    grand_mean = y.mean()
    ss_total = float(((y - grand_mean) ** 2).sum())
    ss_a = sum(len(g) * (g.y.mean() - grand_mean) ** 2 for _, g in df.groupby("fa"))
    ss_b = sum(len(g) * (g.y.mean() - grand_mean) ** 2 for _, g in df.groupby("fb"))
    ss_cells = sum(len(g) * (g.y.mean() - grand_mean) ** 2 for _, g in df.groupby(["fa", "fb"]))
    ss_interaction = ss_cells - ss_a - ss_b
    ss_error = ss_total - ss_cells

    rows_by_source = {r["source"]: r for r in body["table"]}
    assert rows_by_source["fa"]["ss"] == pytest.approx(ss_a)
    assert rows_by_source["fb"]["ss"] == pytest.approx(ss_b)
    assert rows_by_source["fa × fb"]["ss"] == pytest.approx(ss_interaction)
    assert rows_by_source["Résiduelle"]["ss"] == pytest.approx(ss_error)
    assert rows_by_source["fa"]["df"] == 1
    assert rows_by_source["fb"]["df"] == 2
    assert rows_by_source["fa × fb"]["df"] == 2
    assert rows_by_source["Résiduelle"]["df"] == 66
    # L'interaction volontairement injectée doit ressortir.
    assert rows_by_source["fa × fb"]["p_value"] < 0.05


def test_two_way_anova_requires_distinct_factors(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="anova", test="two_way",
                column="mesure", factor_a="groupe", factor_b="groupe")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SAME_COLUMN"


def test_anova_requires_at_least_two_levels():
    df = pd.DataFrame({"f": ["seul"] * 30, "y": range(30)})
    session_id = _upload(df)
    resp = _run(session_id, family="anova", test="one_way", column="y", factor_a="f")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INSUFFICIENT_GROUPS"


# --- Corrélations ------------------------------------------------------------

@pytest.mark.parametrize("test,function", [
    ("pearson", sps.pearsonr), ("spearman", sps.spearmanr), ("kendall", sps.kendalltau),
])
def test_correlation_matches_scipy(dataset, test, function):
    df, session_id = dataset
    body = _run(session_id, family="correlation", test=test,
                column="mesure", column_b="correle").json()
    reference = function(df.mesure, df.correle)
    assert body["test_statistic"] == pytest.approx(float(reference[0]))
    assert body["p_value"] == pytest.approx(float(reference[1]))


def test_pearson_confidence_interval_uses_fisher(dataset):
    df, session_id = dataset
    body = _run(session_id, family="correlation", test="pearson",
                column="mesure", column_b="correle").json()
    r = body["test_statistic"]
    n = body["n_pairs"]
    z = math.atanh(r)
    se = 1 / math.sqrt(n - 3)
    critical = sps.norm.ppf(0.975)
    assert body["confidence_interval"]["low"] == pytest.approx(math.tanh(z - critical * se))
    assert body["confidence_interval"]["high"] == pytest.approx(math.tanh(z + critical * se))


def test_spearman_has_no_confidence_interval(dataset):
    _, session_id = dataset
    body = _run(session_id, family="correlation", test="spearman",
                column="mesure", column_b="correle").json()
    assert body["confidence_interval"]["low"] is None
    assert "Pearson" in body["confidence_interval"]["note"]


def test_correlation_states_causation_caveat(dataset):
    _, session_id = dataset
    body = _run(session_id, family="correlation", test="pearson",
                column="mesure", column_b="correle").json()
    assert "cause à effet" in body["caution"]


def test_correlation_requires_two_distinct_columns(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="correlation", test="pearson",
                column="mesure", column_b="mesure")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "SAME_COLUMN"


# --- Ajustement --------------------------------------------------------------

def test_shapiro_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="goodness_of_fit", test="shapiro", column="mesure").json()
    statistic, p_value = sps.shapiro(df.mesure)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)


def test_ks_matches_scipy_and_states_its_caveat(dataset):
    df, session_id = dataset
    body = _run(session_id, family="goodness_of_fit", test="ks",
                column="avant", distribution="norm").json()
    params = sps.norm.fit(df.avant)
    statistic, p_value = sps.kstest(df.avant, sps.norm.cdf, args=params)
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert "optimiste" in body["caveat"]


def test_anderson_returns_critical_values_not_p_value(dataset):
    _, session_id = dataset
    body = _run(session_id, family="goodness_of_fit", test="anderson", column="avant").json()
    assert body["p_value"] is None
    assert len(body["critical_values"]) == 5
    assert "ne fournit pas de p-value" in body["note"]


def test_chi2_independence_matches_scipy(dataset):
    df, session_id = dataset
    body = _run(session_id, family="goodness_of_fit", test="chi2",
                column="groupe", column_b="bloc").json()
    table = pd.crosstab(df.groupe, df.bloc)
    statistic, p_value, dof, _ = sps.chi2_contingency(table.to_numpy())
    assert body["test_statistic"] == pytest.approx(statistic)
    assert body["p_value"] == pytest.approx(p_value)
    assert body["degrees_of_freedom"] == dof


def test_cramers_v_matches_formula(dataset):
    df, session_id = dataset
    body = _run(session_id, family="goodness_of_fit", test="chi2",
                column="groupe", column_b="bloc").json()
    table = pd.crosstab(df.groupe, df.bloc)
    statistic = sps.chi2_contingency(table.to_numpy())[0]
    n = table.to_numpy().sum()
    expected = math.sqrt(statistic / (n * (min(table.shape) - 1)))
    assert body["effect_size"]["value"] == pytest.approx(expected)


def test_normality_verdict_on_normal_and_skewed_data():
    rng = np.random.default_rng(63)
    df = pd.DataFrame({"normale": rng.normal(0, 1, 400), "asymetrique": rng.exponential(3, 400)})
    session_id = _upload(df)
    normal = _run(session_id, family="goodness_of_fit", test="shapiro", column="normale").json()
    skewed = _run(session_id, family="goodness_of_fit", test="shapiro", column="asymetrique").json()
    assert normal["decision"]["significant"] is False   # normalité non rejetée
    assert skewed["decision"]["significant"] is True    # normalité rejetée


# --- Garde-fous généraux -----------------------------------------------------

def test_test_must_belong_to_its_family(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="anova", test="pearson", column="mesure")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TEST_FAMILY_MISMATCH"


def test_alpha_must_be_between_zero_and_one(dataset):
    _, session_id = dataset
    resp = _run(session_id, family="hypothesis", test="ttest_1samp", column="mesure", alpha=1.5)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ALPHA"


def test_every_result_carries_an_effect_size(dataset):
    _, session_id = dataset
    cases = [
        {"family": "hypothesis", "test": "ttest_ind", "column": "mesure",
         "group_column": "groupe", "group_a": "a", "group_b": "b"},
        {"family": "anova", "test": "one_way", "column": "mesure", "factor_a": "groupe"},
        {"family": "correlation", "test": "pearson", "column": "mesure", "column_b": "correle"},
        {"family": "goodness_of_fit", "test": "shapiro", "column": "mesure"},
    ]
    for case in cases:
        body = _run(session_id, **case).json()
        effect = body["effect_size"]
        assert effect["value"] is not None
        assert effect["definition"] and effect["magnitude"]
        assert body["figure"] is not None


def test_hypothesis_test_session_not_found():
    resp = client.post("/api/stats/hypothesis_test", json={"session_id": "inconnue", "column": "a"})
    assert resp.status_code == 404
