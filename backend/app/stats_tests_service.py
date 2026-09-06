"""Tests statistiques (Phase 8).

Chaque test renvoie sa statistique, sa p-value, une taille d'effet et une
interprétation rédigée. La taille d'effet est systématique et non optionnelle :
une p-value seule dit si un écart est détectable, jamais s'il est important —
sur un grand échantillon, un écart négligeable devient « significatif ».
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats as sps

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type
from app.plotting_service import DEFAULT_QUALITATIVE, _with_alpha

NUMERIC_TYPES = ("integer", "float")
MAX_GROUPS = 20
MIN_SAMPLE = 3


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def _require_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise column_not_found(column)
    if detect_column_type(df[column]) not in NUMERIC_TYPES:
        raise AppError(400, "INVALID_COLUMN_TYPE",
                       f"La colonne '{column}' doit être numérique pour ce test.")
    return pd.to_numeric(df[column], errors="coerce")


def _require_column(df: pd.DataFrame, column: Optional[str], role: str) -> str:
    if not column:
        raise AppError(400, "MISSING_COLUMN", f"La colonne « {role} » est requise pour ce test.")
    if column not in df.columns:
        raise column_not_found(column)
    return column


def _two_samples(df: pd.DataFrame, column: str, group_column: str,
                 group_a: Optional[str], group_b: Optional[str]) -> tuple[np.ndarray, np.ndarray, str, str]:
    """Extrait deux échantillons d'une colonne numérique, séparés par une modalité."""
    values = _require_numeric(df, column)
    groups = df[group_column].astype(str)
    levels = [lvl for lvl in groups.dropna().unique()]

    if group_a is None or group_b is None:
        if len(levels) != 2:
            raise AppError(
                400, "AMBIGUOUS_GROUPS",
                f"La colonne '{group_column}' contient {len(levels)} modalités : "
                "précisez les deux groupes à comparer.",
            )
        group_a, group_b = levels[0], levels[1]

    for level in (group_a, group_b):
        if level not in levels:
            raise AppError(400, "GROUP_NOT_FOUND",
                           f"La modalité '{level}' est absente de la colonne '{group_column}'.")
    if group_a == group_b:
        raise AppError(400, "SAME_GROUP", "Les deux groupes comparés doivent être différents.")

    frame = pd.DataFrame({"value": values, "group": groups}).dropna()
    a = frame.loc[frame["group"] == group_a, "value"].to_numpy(dtype=float)
    b = frame.loc[frame["group"] == group_b, "value"].to_numpy(dtype=float)
    for sample, name in ((a, group_a), (b, group_b)):
        if sample.size < MIN_SAMPLE:
            raise AppError(422, "INSUFFICIENT_DATA",
                           f"Le groupe '{name}' ne compte que {sample.size} observation(s) valides "
                           f"(minimum {MIN_SAMPLE}).")
    return a, b, str(group_a), str(group_b)


def _paired_samples(df: pd.DataFrame, column_a: str, column_b: str) -> tuple[np.ndarray, np.ndarray]:
    a = _require_numeric(df, column_a)
    b = _require_numeric(df, column_b)
    pair = pd.DataFrame({"a": a, "b": b}).dropna()
    if pair.shape[0] < MIN_SAMPLE:
        raise AppError(422, "INSUFFICIENT_DATA",
                       "Trop peu de paires complètes pour un test apparié "
                       f"({pair.shape[0]}, minimum {MIN_SAMPLE}).")
    return pair["a"].to_numpy(dtype=float), pair["b"].to_numpy(dtype=float)


# --------------------------------------------------------------------------
# Tailles d'effet
# --------------------------------------------------------------------------

def _cohens_d(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Différence des moyennes en écarts-types (d de Cohen) et sa version corrigée."""
    n1, n2 = a.size, b.size
    pooled_var = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
    pooled_sd = math.sqrt(pooled_var) if pooled_var > 0 else 0.0
    d = (a.mean() - b.mean()) / pooled_sd if pooled_sd > 0 else 0.0
    # Correction de Hedges : le d de Cohen surestime l'effet sur petits échantillons.
    correction = 1 - 3 / (4 * (n1 + n2) - 9) if (n1 + n2) > 3 else 1.0
    return d, d * correction


def _rank_biserial(u_statistic: float, n1: int, n2: int) -> float:
    """Corrélation bisériale de rang : proportion de paires favorables, centrée."""
    return 2 * u_statistic / (n1 * n2) - 1


def _interpret_magnitude(value: float, thresholds: tuple[float, float, float], labels: tuple[str, ...]) -> str:
    magnitude = abs(value)
    small, medium, large = thresholds
    if magnitude < small:
        return labels[0]
    if magnitude < medium:
        return labels[1]
    if magnitude < large:
        return labels[2]
    return labels[3]


COHEN_LABELS = ("négligeable", "petit", "moyen", "grand")
COHEN_THRESHOLDS = (0.2, 0.5, 0.8)


def _decision(p_value: Optional[float], alpha: float, null_hypothesis: str) -> dict[str, Any]:
    if p_value is None:
        return {
            "significant": None,
            "text": "La p-value n'a pas pu être calculée pour ces données.",
        }
    significant = p_value < alpha
    if significant:
        text = (f"p = {p_value:.4g} < α = {alpha} : l'hypothèse nulle « {null_hypothesis} » est rejetée. "
                "L'écart observé est trop marqué pour être attribué au seul hasard d'échantillonnage.")
    else:
        text = (f"p = {p_value:.4g} ≥ α = {alpha} : l'hypothèse nulle « {null_hypothesis} » n'est pas rejetée. "
                "Attention : ne pas rejeter n'est pas démontrer l'absence d'effet — "
                "un échantillon trop petit produit le même résultat qu'une absence réelle d'écart.")
    return {"significant": bool(significant), "text": text}


# --------------------------------------------------------------------------
# Famille 1 : comparaisons de deux échantillons
# --------------------------------------------------------------------------

def _hypothesis_test(df: pd.DataFrame, req) -> dict[str, Any]:
    test = req.test
    alpha = req.alpha
    alternative = req.alternative

    if test == "ttest_1samp":
        values = _require_numeric(df, _require_column(df, req.column, "colonne")).dropna().to_numpy(dtype=float)
        if values.size < MIN_SAMPLE:
            raise AppError(422, "INSUFFICIENT_DATA", "Trop peu d'observations valides pour ce test.")
        statistic, p_value = sps.ttest_1samp(values, req.popmean, alternative=alternative)
        effect = (values.mean() - req.popmean) / values.std(ddof=1) if values.std(ddof=1) > 0 else 0.0
        return {
            "test_name": "Test t sur un échantillon",
            "null_hypothesis": f"la moyenne vaut {req.popmean}",
            "test_statistic": _num(statistic),
            "degrees_of_freedom": int(values.size - 1),
            "p_value": _num(p_value),
            "effect_size": {
                "name": "d de Cohen",
                "value": _num(effect),
                "magnitude": _interpret_magnitude(effect, COHEN_THRESHOLDS, COHEN_LABELS),
                "definition": "Écart entre la moyenne observée et la valeur de référence, exprimé en écarts-types.",
            },
            "samples": [{"label": req.column, "n": int(values.size),
                         "mean": _num(values.mean()), "std": _num(values.std(ddof=1)),
                         "median": _num(np.median(values))}],
            "decision": _decision(_num(p_value), alpha, f"la moyenne vaut {req.popmean}"),
            "_figure": _distribution_figure([(req.column, values)], reference=req.popmean),
        }

    if test in ("ttest_rel", "wilcoxon"):
        column_a = _require_column(df, req.column, "première colonne")
        column_b = _require_column(df, req.column_b, "seconde colonne")
        a, b = _paired_samples(df, column_a, column_b)
        differences = a - b

        if test == "ttest_rel":
            statistic, p_value = sps.ttest_rel(a, b, alternative=alternative)
            sd = differences.std(ddof=1)
            effect_value = differences.mean() / sd if sd > 0 else 0.0
            effect = {
                "name": "d de Cohen (apparié)",
                "value": _num(effect_value),
                "magnitude": _interpret_magnitude(effect_value, COHEN_THRESHOLDS, COHEN_LABELS),
                "definition": "Moyenne des différences appariées, exprimée en écarts-types de ces différences.",
            }
            name = "Test t apparié"
            null = "les deux mesures ont la même moyenne"
        else:
            non_zero = differences[differences != 0]
            if non_zero.size < MIN_SAMPLE:
                raise AppError(422, "INSUFFICIENT_DATA",
                               "Trop peu de différences non nulles pour un test de Wilcoxon.")
            statistic, p_value = sps.wilcoxon(a, b, alternative=alternative)
            n = non_zero.size
            max_statistic = n * (n + 1) / 2
            effect_value = 1 - 2 * statistic / max_statistic
            effect = {
                "name": "Corrélation bisériale de rang",
                "value": _num(effect_value),
                "magnitude": _interpret_magnitude(effect_value, (0.1, 0.3, 0.5),
                                                  ("négligeable", "petite", "moyenne", "grande")),
                "definition": "Déséquilibre entre différences positives et négatives, de −1 à +1.",
            }
            name = "Test des rangs signés de Wilcoxon"
            null = "les différences appariées sont réparties symétriquement autour de zéro"

        return {
            "test_name": name,
            "null_hypothesis": null,
            "test_statistic": _num(statistic),
            "degrees_of_freedom": int(a.size - 1) if test == "ttest_rel" else None,
            "p_value": _num(p_value),
            "effect_size": effect,
            "samples": [
                {"label": column_a, "n": int(a.size), "mean": _num(a.mean()),
                 "std": _num(a.std(ddof=1)), "median": _num(np.median(a))},
                {"label": column_b, "n": int(b.size), "mean": _num(b.mean()),
                 "std": _num(b.std(ddof=1)), "median": _num(np.median(b))},
            ],
            "n_pairs": int(a.size),
            "decision": _decision(_num(p_value), alpha, null),
            "_figure": _distribution_figure([(column_a, a), (column_b, b)]),
        }

    # Tests à deux échantillons indépendants
    column = _require_column(df, req.column, "colonne mesurée")
    group_column = _require_column(df, req.group_column, "colonne de groupes")
    a, b, label_a, label_b = _two_samples(df, column, group_column, req.group_a, req.group_b)

    if test == "ttest_ind":
        # Welch par défaut : ne suppose pas l'égalité des variances, ce qui est
        # le cas général sur des données réelles.
        statistic, p_value = sps.ttest_ind(a, b, equal_var=req.equal_variance, alternative=alternative)
        d, hedges = _cohens_d(a, b)
        effect = {
            "name": "d de Cohen",
            "value": _num(d),
            "corrected_value": _num(hedges),
            "magnitude": _interpret_magnitude(d, COHEN_THRESHOLDS, COHEN_LABELS),
            "definition": "Écart entre les deux moyennes, exprimé en écarts-types. "
                          "La valeur corrigée (g de Hedges) retire le biais des petits échantillons.",
        }
        name = "Test t de Welch" if not req.equal_variance else "Test t de Student"
        null = f"les moyennes de « {label_a} » et « {label_b} » sont égales"
        dof = _num(sps.ttest_ind(a, b, equal_var=req.equal_variance).df) if hasattr(
            sps.ttest_ind(a, b, equal_var=req.equal_variance), "df") else None
    elif test == "mannwhitney":
        statistic, p_value = sps.mannwhitneyu(a, b, alternative=alternative)
        effect_value = _rank_biserial(float(statistic), a.size, b.size)
        effect = {
            "name": "Corrélation bisériale de rang",
            "value": _num(effect_value),
            "magnitude": _interpret_magnitude(effect_value, (0.1, 0.3, 0.5),
                                              ("négligeable", "petite", "moyenne", "grande")),
            "definition": "Probabilité qu'une valeur du premier groupe dépasse une valeur du second, "
                          "ramenée à l'intervalle −1 à +1.",
        }
        name = "Test U de Mann-Whitney"
        null = f"les distributions de « {label_a} » et « {label_b} » sont identiques"
        dof = None
    else:  # pragma: no cover - garanti par Literal
        raise AppError(400, "UNKNOWN_TEST", f"Test inconnu : {test}")

    return {
        "test_name": name,
        "null_hypothesis": null,
        "test_statistic": _num(statistic),
        "degrees_of_freedom": dof,
        "p_value": _num(p_value),
        "effect_size": effect,
        "samples": [
            {"label": label_a, "n": int(a.size), "mean": _num(a.mean()),
             "std": _num(a.std(ddof=1)), "median": _num(np.median(a))},
            {"label": label_b, "n": int(b.size), "mean": _num(b.mean()),
             "std": _num(b.std(ddof=1)), "median": _num(np.median(b))},
        ],
        "normality_note": _normality_note(a, b, test),
        "decision": _decision(_num(p_value), alpha, null),
        "_figure": _distribution_figure([(label_a, a), (label_b, b)]),
    }


def _normality_note(a: np.ndarray, b: np.ndarray, test: str) -> Optional[str]:
    """Signale quand un test paramétrique s'applique à des données non normales."""
    if test != "ttest_ind":
        return None
    try:
        p_a = sps.shapiro(a[:5000])[1]
        p_b = sps.shapiro(b[:5000])[1]
    except (ValueError, FloatingPointError):
        return None
    if min(p_a, p_b) < 0.05 and min(a.size, b.size) < 30:
        return ("Les données s'écartent de la normalité (Shapiro-Wilk : "
                f"p = {min(p_a, p_b):.4g}) et les échantillons sont petits. "
                "Le test de Mann-Whitney, qui ne suppose pas la normalité, serait plus fiable ici.")
    if min(p_a, p_b) < 0.05:
        return ("Les données s'écartent de la normalité (Shapiro-Wilk : "
                f"p = {min(p_a, p_b):.4g}), mais les échantillons sont assez grands pour que "
                "le test t reste valide par le théorème central limite.")
    return None


# --------------------------------------------------------------------------
# Famille 2 : ANOVA
# --------------------------------------------------------------------------

def _design_matrix(frame: pd.DataFrame, factors: list[str], interaction: bool) -> np.ndarray:
    """Matrice de conception : constante + indicatrices (première modalité omise)."""
    n = frame.shape[0]
    blocks = [np.ones((n, 1))]
    dummies_per_factor = []
    for factor in factors:
        dummies = pd.get_dummies(frame[factor].astype(str), drop_first=True).to_numpy(dtype=float)
        dummies_per_factor.append(dummies)
        if dummies.size:
            blocks.append(dummies)
    if interaction and len(dummies_per_factor) == 2:
        left, right = dummies_per_factor
        if left.size and right.size:
            products = np.einsum("ij,ik->ijk", left, right).reshape(n, -1)
            blocks.append(products)
    return np.hstack(blocks)


def _residual_sum_of_squares(design: np.ndarray, y: np.ndarray) -> tuple[float, int]:
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    residuals = y - design @ coefficients
    return float(residuals @ residuals), int(np.linalg.matrix_rank(design))


def _anova(df: pd.DataFrame, req) -> dict[str, Any]:
    column = _require_column(df, req.column, "colonne mesurée")
    values = _require_numeric(df, column)
    factor_a = _require_column(df, req.factor_a or req.group_column, "premier facteur")

    factors = [factor_a]
    if req.test == "two_way":
        factor_b = _require_column(df, req.factor_b, "second facteur")
        if factor_b == factor_a:
            raise AppError(400, "SAME_COLUMN", "Les deux facteurs doivent être des colonnes différentes.")
        factors.append(factor_b)

    frame = pd.DataFrame({column: values, **{f: df[f].astype(str) for f in factors}}).dropna()
    for factor in factors:
        levels = frame[factor].nunique()
        if levels < 2:
            raise AppError(422, "INSUFFICIENT_GROUPS",
                           f"Le facteur '{factor}' doit avoir au moins 2 modalités (il en a {levels}).")
        if levels > MAX_GROUPS:
            raise AppError(422, "TOO_MANY_GROUPS",
                           f"Le facteur '{factor}' a {levels} modalités (maximum {MAX_GROUPS}).")
    if frame.shape[0] < MIN_SAMPLE * 2:
        raise AppError(422, "INSUFFICIENT_DATA", "Trop peu d'observations complètes pour une ANOVA.")

    y = frame[column].to_numpy(dtype=float)
    grand_mean = y.mean()
    ss_total = float(((y - grand_mean) ** 2).sum())

    if req.test == "one_way":
        samples = [group[column].to_numpy(dtype=float) for _, group in frame.groupby(factor_a)]
        labels = [str(name) for name, _ in frame.groupby(factor_a)]
        if any(sample.size < 2 for sample in samples):
            raise AppError(422, "INSUFFICIENT_DATA",
                           "Chaque groupe doit compter au moins 2 observations pour une ANOVA.")
        statistic, p_value = sps.f_oneway(*samples)

        df_between = len(samples) - 1
        df_within = int(y.size - len(samples))
        ss_within = float(sum(((s - s.mean()) ** 2).sum() for s in samples))
        ss_between = ss_total - ss_within
        ms_within = ss_within / df_within if df_within else 0.0

        eta_squared = ss_between / ss_total if ss_total > 0 else 0.0
        omega_squared = ((ss_between - df_between * ms_within) / (ss_total + ms_within)
                         if (ss_total + ms_within) > 0 else 0.0)

        table = [
            {"source": factor_a, "ss": _num(ss_between), "df": df_between,
             "ms": _num(ss_between / df_between if df_between else None),
             "f": _num(statistic), "p_value": _num(p_value)},
            {"source": "Résiduelle", "ss": _num(ss_within), "df": df_within,
             "ms": _num(ms_within), "f": None, "p_value": None},
        ]
        null = f"toutes les modalités de « {factor_a} » ont la même moyenne"
        result = {
            "test_name": "ANOVA à un facteur",
            "null_hypothesis": null,
            "test_statistic": _num(statistic),
            "degrees_of_freedom": [df_between, df_within],
            "p_value": _num(p_value),
            "effect_size": {
                "name": "η² (eta carré)",
                "value": _num(eta_squared),
                "corrected_value": _num(omega_squared),
                "magnitude": _interpret_magnitude(eta_squared, (0.01, 0.06, 0.14),
                                                  ("négligeable", "petit", "moyen", "grand")),
                "definition": "Part de la variance de la mesure expliquée par le facteur. "
                              "ω² corrige le biais optimiste de η² sur petits échantillons.",
            },
            "table": table,
            "groups": [
                {"label": label, "n": int(sample.size), "mean": _num(sample.mean()),
                 "std": _num(sample.std(ddof=1)) if sample.size > 1 else 0.0}
                for label, sample in zip(labels, samples)
            ],
            "post_hoc": _post_hoc(samples, labels, req.post_hoc, req.alpha),
            "homogeneity": _levene_note(samples),
            "decision": _decision(_num(p_value), req.alpha, null),
            "_figure": _box_figure(list(zip(labels, samples)), column, factor_a),
        }
        return result

    # ANOVA à deux facteurs : sommes de carrés de type II, par comparaison de
    # modèles emboîtés (l'effet d'un facteur est mesuré l'autre déjà pris en compte).
    factor_b = factors[1]
    design_full = _design_matrix(frame, factors, interaction=True)
    design_additive = _design_matrix(frame, factors, interaction=False)
    design_a = _design_matrix(frame, [factor_a], interaction=False)
    design_b = _design_matrix(frame, [factor_b], interaction=False)

    rss_full, rank_full = _residual_sum_of_squares(design_full, y)
    rss_additive, rank_additive = _residual_sum_of_squares(design_additive, y)
    rss_a, rank_a = _residual_sum_of_squares(design_a, y)
    rss_b, rank_b = _residual_sum_of_squares(design_b, y)

    df_residual = int(y.size - rank_full)
    if df_residual <= 0:
        raise AppError(422, "INSUFFICIENT_DATA",
                       "Le modèle a autant de paramètres que d'observations : "
                       "il n'y a plus de degrés de liberté pour estimer l'erreur.")
    ms_residual = rss_full / df_residual

    def effect_row(source: str, ss: float, df_effect: int) -> dict[str, Any]:
        if df_effect <= 0 or ms_residual <= 0:
            return {"source": source, "ss": _num(ss), "df": df_effect, "ms": None, "f": None, "p_value": None}
        ms = ss / df_effect
        f_value = ms / ms_residual
        return {
            "source": source, "ss": _num(ss), "df": df_effect, "ms": _num(ms),
            "f": _num(f_value), "p_value": _num(sps.f.sf(f_value, df_effect, df_residual)),
        }

    ss_a = rss_b - rss_additive
    ss_b = rss_a - rss_additive
    ss_interaction = rss_additive - rss_full
    rows = [
        effect_row(factor_a, ss_a, rank_additive - rank_b),
        effect_row(factor_b, ss_b, rank_additive - rank_a),
        effect_row(f"{factor_a} × {factor_b}", ss_interaction, rank_full - rank_additive),
        {"source": "Résiduelle", "ss": _num(rss_full), "df": df_residual,
         "ms": _num(ms_residual), "f": None, "p_value": None},
    ]

    main_p = [r["p_value"] for r in rows[:3] if r["p_value"] is not None]
    smallest_p = min(main_p) if main_p else None
    eta_a = ss_a / ss_total if ss_total > 0 else 0.0
    null = f"ni « {factor_a} », ni « {factor_b} », ni leur interaction n'influencent la mesure"

    return {
        "test_name": "ANOVA à deux facteurs (sommes de carrés de type II)",
        "null_hypothesis": null,
        "test_statistic": rows[0]["f"],
        "degrees_of_freedom": [rows[0]["df"], df_residual],
        "p_value": smallest_p,
        "effect_size": {
            "name": f"η² de {factor_a}",
            "value": _num(eta_a),
            "magnitude": _interpret_magnitude(eta_a, (0.01, 0.06, 0.14),
                                              ("négligeable", "petit", "moyen", "grand")),
            "definition": "Part de la variance expliquée par le premier facteur. "
                          "Le tableau détaille chaque source séparément.",
        },
        "table": rows,
        "groups": [
            {"label": f"{a} · {b}", "n": int(group.shape[0]),
             "mean": _num(group[column].mean()),
             "std": _num(group[column].std(ddof=1)) if group.shape[0] > 1 else 0.0}
            for (a, b), group in frame.groupby([factor_a, factor_b])
        ],
        "post_hoc": None,
        "interaction_note": (
            "L'interaction teste si l'effet d'un facteur dépend du niveau de l'autre. "
            "Quand elle est significative, les effets principaux ne s'interprètent plus isolément."
        ),
        "decision": _decision(smallest_p, req.alpha, null),
        "_figure": _grouped_box_figure(frame, column, factor_a, factor_b),
    }


def _levene_note(samples: list[np.ndarray]) -> Optional[dict]:
    """Test de Levene : l'ANOVA suppose des variances comparables entre groupes."""
    try:
        statistic, p_value = sps.levene(*samples, center="median")
    except (ValueError, FloatingPointError):
        return None
    homogeneous = p_value >= 0.05
    return {
        "test": "Levene",
        "statistic": _num(statistic),
        "p_value": _num(p_value),
        "homogeneous": bool(homogeneous),
        "note": ("Les variances des groupes sont comparables : l'hypothèse d'homoscédasticité de "
                 "l'ANOVA est satisfaite.")
        if homogeneous else
        ("Les variances diffèrent significativement entre groupes (p = "
         f"{p_value:.4g}). L'ANOVA classique devient peu fiable, en particulier si les effectifs "
         "sont déséquilibrés ; un test de Kruskal-Wallis serait plus prudent."),
    }


def _post_hoc(samples: list[np.ndarray], labels: list[str], method: str, alpha: float) -> Optional[dict]:
    """Comparaisons deux à deux après une ANOVA significative."""
    if method == "none" or len(samples) < 3:
        return None

    comparisons = []
    if method == "tukey":
        result = sps.tukey_hsd(*samples)
        interval = result.confidence_interval(confidence_level=1 - alpha)
        for i in range(len(samples)):
            for j in range(i + 1, len(samples)):
                comparisons.append({
                    "group_a": labels[i], "group_b": labels[j],
                    "difference": _num(samples[i].mean() - samples[j].mean()),
                    "statistic": _num(result.statistic[i, j]),
                    "p_value": _num(result.pvalue[i, j]),
                    "ci_low": _num(interval.low[i, j]),
                    "ci_high": _num(interval.high[i, j]),
                    "significant": bool(result.pvalue[i, j] < alpha),
                })
        description = ("Tukey HSD compare toutes les paires en contrôlant le risque global d'erreur : "
                       "les p-values sont déjà ajustées.")
    else:  # bonferroni
        pairs = [(i, j) for i in range(len(samples)) for j in range(i + 1, len(samples))]
        n_comparisons = len(pairs)
        for i, j in pairs:
            statistic, raw_p = sps.ttest_ind(samples[i], samples[j], equal_var=False)
            adjusted = min(1.0, float(raw_p) * n_comparisons)
            comparisons.append({
                "group_a": labels[i], "group_b": labels[j],
                "difference": _num(samples[i].mean() - samples[j].mean()),
                "statistic": _num(statistic),
                "p_value": _num(adjusted),
                "raw_p_value": _num(raw_p),
                "ci_low": None, "ci_high": None,
                "significant": bool(adjusted < alpha),
            })
        description = (f"Bonferroni multiplie chaque p-value par le nombre de comparaisons "
                       f"({n_comparisons}). Correction simple mais conservatrice : elle rate des écarts réels "
                       "quand les comparaisons sont nombreuses.")

    return {"method": method, "description": description, "comparisons": comparisons}


# --------------------------------------------------------------------------
# Famille 3 : tests de corrélation
# --------------------------------------------------------------------------

CORRELATION_TESTS = {
    "pearson": ("Corrélation de Pearson", sps.pearsonr,
                "il n'existe aucune relation linéaire entre les deux variables"),
    "spearman": ("Corrélation de Spearman", sps.spearmanr,
                 "il n'existe aucune relation monotone entre les deux variables"),
    "kendall": ("Tau de Kendall", sps.kendalltau,
                "les deux variables sont indépendantes en termes de concordance de rangs"),
}


def _fisher_confidence_interval(r: float, n: int, alpha: float) -> tuple[Optional[float], Optional[float]]:
    """Intervalle de confiance d'un coefficient via la transformation z de Fisher."""
    if n < 4 or abs(r) >= 1:
        return None, None
    z = math.atanh(r)
    standard_error = 1 / math.sqrt(n - 3)
    critical = sps.norm.ppf(1 - alpha / 2)
    return math.tanh(z - critical * standard_error), math.tanh(z + critical * standard_error)


def _correlation_test(df: pd.DataFrame, req) -> dict[str, Any]:
    column_a = _require_column(df, req.column, "première variable")
    column_b = _require_column(df, req.column_b, "seconde variable")
    if column_a == column_b:
        raise AppError(400, "SAME_COLUMN", "Choisissez deux colonnes différentes.")

    a = _require_numeric(df, column_a)
    b = _require_numeric(df, column_b)
    pair = pd.DataFrame({"a": a, "b": b}).dropna()
    if pair.shape[0] < 4:
        raise AppError(422, "INSUFFICIENT_DATA",
                       f"Seulement {pair.shape[0]} paires complètes : au moins 4 sont nécessaires.")

    x = pair["a"].to_numpy(dtype=float)
    y = pair["b"].to_numpy(dtype=float)
    name, function, null = CORRELATION_TESTS[req.test]
    result = function(x, y)
    r, p_value = float(result[0]), float(result[1])

    ci_low, ci_high = (_fisher_confidence_interval(r, x.size, req.alpha)
                       if req.test == "pearson" else (None, None))

    # Droite d'ajustement, à titre indicatif : elle n'a de sens que pour Pearson.
    slope, intercept = np.polyfit(x, y, 1)
    grid = np.linspace(x.min(), x.max(), 100)

    return {
        "test_name": name,
        "null_hypothesis": null,
        "test_statistic": _num(r),
        "p_value": _num(p_value),
        "n_pairs": int(x.size),
        "effect_size": {
            "name": "Coefficient de corrélation",
            "value": _num(r),
            "corrected_value": _num(r ** 2) if req.test == "pearson" else None,
            "magnitude": _interpret_magnitude(r, (0.1, 0.3, 0.5),
                                              ("négligeable", "faible", "modérée", "forte")),
            "definition": "Le coefficient est lui-même la taille d'effet."
                          + (" Son carré (r²) donne la part de variance partagée."
                             if req.test == "pearson" else ""),
        },
        "confidence_interval": {
            "level": 1 - req.alpha,
            "low": _num(ci_low),
            "high": _num(ci_high),
            "note": "Intervalle obtenu par la transformation z de Fisher."
            if ci_low is not None else
            "Intervalle de confiance disponible uniquement pour la corrélation de Pearson.",
        },
        "caution": "Une corrélation ne démontre pas de lien de cause à effet, et un coefficient proche "
                   "de zéro n'exclut pas une relation non linéaire.",
        "decision": _decision(_num(p_value), req.alpha, null),
        "_figure": _scatter_figure(x, y, column_a, column_b, grid, slope * grid + intercept, r),
    }


# --------------------------------------------------------------------------
# Famille 4 : tests d'ajustement
# --------------------------------------------------------------------------

GOODNESS_DISTRIBUTIONS = {
    "norm": ("normale", sps.norm),
    "expon": ("exponentielle", sps.expon),
    "uniform": ("uniforme", sps.uniform),
    "lognorm": ("log-normale", sps.lognorm),
}


def _goodness_of_fit(df: pd.DataFrame, req) -> dict[str, Any]:
    column = _require_column(df, req.column, "colonne")
    test = req.test

    if test == "chi2":
        # Deux colonnes catégorielles : test d'indépendance sur table de contingence.
        column_b = _require_column(df, req.column_b, "seconde colonne")
        table = pd.crosstab(df[column].astype(str), df[column_b].astype(str))
        if table.shape[0] < 2 or table.shape[1] < 2:
            raise AppError(422, "INSUFFICIENT_GROUPS",
                           "Le test du khi² d'indépendance demande au moins 2 modalités par colonne.")
        statistic, p_value, dof, expected = sps.chi2_contingency(table.to_numpy())
        n = int(table.to_numpy().sum())
        min_dimension = min(table.shape) - 1
        cramers_v = math.sqrt(statistic / (n * min_dimension)) if n and min_dimension else 0.0
        low_expected = int((expected < 5).sum())
        null = f"« {column} » et « {column_b} » sont indépendantes"
        return {
            "test_name": "Test du khi² d'indépendance",
            "null_hypothesis": null,
            "test_statistic": _num(statistic),
            "degrees_of_freedom": int(dof),
            "p_value": _num(p_value),
            "effect_size": {
                "name": "V de Cramér",
                "value": _num(cramers_v),
                "magnitude": _interpret_magnitude(cramers_v, (0.1, 0.3, 0.5),
                                                  ("négligeable", "faible", "modérée", "forte")),
                "definition": "Intensité de l'association entre deux variables catégorielles, de 0 à 1.",
            },
            "contingency": {
                "rows": [str(i) for i in table.index],
                "columns": [str(c) for c in table.columns],
                "observed": table.to_numpy().tolist(),
                "expected": np.round(expected, 2).tolist(),
            },
            "assumption_note": (
                f"{low_expected} cellule(s) ont un effectif théorique inférieur à 5 : "
                "l'approximation du khi² devient imprécise. Regroupez des modalités rares "
                "ou utilisez un test exact."
            ) if low_expected else None,
            "decision": _decision(_num(p_value), req.alpha, null),
            "_figure": _contingency_figure(table),
        }

    values = _require_numeric(df, column).dropna().to_numpy(dtype=float)
    if values.size < MIN_SAMPLE:
        raise AppError(422, "INSUFFICIENT_DATA", "Trop peu d'observations valides pour ce test.")

    distribution_key = req.distribution
    distribution_label, distribution = GOODNESS_DISTRIBUTIONS[distribution_key]

    if test == "shapiro":
        sample = values if values.size <= 5000 else np.random.default_rng(42).choice(values, 5000, replace=False)
        statistic, p_value = sps.shapiro(sample)
        name, null = "Test de Shapiro-Wilk", "l'échantillon suit une loi normale"
        extra = {"sampled": bool(values.size > 5000), "n_used": int(sample.size)}
    elif test == "ks":
        params = distribution.fit(values)
        statistic, p_value = sps.kstest(values, distribution.cdf, args=params)
        name = f"Test de Kolmogorov-Smirnov (loi {distribution_label})"
        null = f"l'échantillon suit une loi {distribution_label}"
        extra = {
            "fitted_params": [_num(p) for p in params],
            "caveat": "Les paramètres de la loi sont estimés sur l'échantillon lui-même : "
                      "la p-value est alors optimiste et doit être lue comme un indice, "
                      "non comme une validation formelle.",
        }
    else:  # anderson
        result = sps.anderson(values, dist=distribution_key if distribution_key in ("norm", "expon") else "norm")
        statistic = float(result.statistic)
        levels = [float(v) for v in result.significance_level]
        criticals = [float(v) for v in result.critical_values]
        # Anderson-Darling ne renvoie pas de p-value : on encadre par les seuils.
        p_value = None
        exceeded = [lvl for lvl, crit in zip(levels, criticals) if statistic > crit]
        name = f"Test d'Anderson-Darling (loi {distribution_label})"
        null = f"l'échantillon suit une loi {distribution_label}"
        extra = {
            "critical_values": [{"significance_level": lvl, "critical_value": crit,
                                 "rejected": bool(statistic > crit)}
                                for lvl, crit in zip(levels, criticals)],
            "note": "Ce test ne fournit pas de p-value : la statistique est comparée à des valeurs "
                    "critiques tabulées. "
                    + (f"L'hypothèse est rejetée jusqu'au seuil de {min(exceeded)} %."
                       if exceeded else "L'hypothèse n'est rejetée à aucun des seuils usuels."),
        }

    skewness = float(sps.skew(values))
    result_payload = {
        "test_name": name,
        "null_hypothesis": null,
        "test_statistic": _num(statistic),
        "p_value": _num(p_value),
        "n": int(values.size),
        "effect_size": {
            "name": "Asymétrie de l'échantillon",
            "value": _num(skewness),
            "magnitude": _interpret_magnitude(skewness, (0.5, 1.0, 2.0),
                                              ("symétrique", "légère", "marquée", "forte")),
            "definition": "Un test d'ajustement n'a pas de taille d'effet standard : l'asymétrie "
                          "indique à quel point la forme observée s'écarte d'une loi symétrique.",
        },
        "decision": _decision(_num(p_value), req.alpha, null) if p_value is not None else {
            "significant": None,
            "text": extra.get("note", "Comparez la statistique aux valeurs critiques tabulées."),
        },
        "_figure": _fit_figure(values, distribution, column, distribution_label, test),
    }
    result_payload.update(extra)
    return result_payload


# --------------------------------------------------------------------------
# Visualisations associées
# --------------------------------------------------------------------------

def _distribution_figure(samples: list[tuple[str, np.ndarray]], reference: Optional[float] = None) -> go.Figure:
    """Densité et box plot superposés : la forme des distributions comparées."""
    fig = go.Figure()
    for i, (label, values) in enumerate(samples):
        color = DEFAULT_QUALITATIVE[i % len(DEFAULT_QUALITATIVE)]
        fig.add_trace(go.Violin(
            x=values, name=label, orientation="h", side="positive",
            line_color=color, fillcolor=_with_alpha(color, 0.35),
            box_visible=True, meanline_visible=True, points=False,
            hovertemplate=f"{label}<br>%{{x:.4g}}<extra></extra>",
        ))
        fig.add_vline(x=float(values.mean()), line=dict(color=color, dash="dash", width=1.5),
                      annotation_text=f"moyenne {label} = {values.mean():.4g}",
                      annotation_position="top")
    if reference is not None:
        fig.add_vline(x=reference, line=dict(color="#E45756", width=2),
                      annotation_text=f"référence = {reference:g}", annotation_position="bottom")
    fig.update_layout(
        title="Distributions comparées",
        margin=dict(t=60, r=20, b=50, l=110),
        xaxis_title="Valeur",
        showlegend=False,
    )
    return fig


def _box_figure(samples: list[tuple[str, np.ndarray]], column: str, factor: str) -> go.Figure:
    fig = go.Figure()
    for i, (label, values) in enumerate(samples):
        fig.add_trace(go.Box(
            y=values, name=label, boxmean="sd",
            marker_color=DEFAULT_QUALITATIVE[i % len(DEFAULT_QUALITATIVE)],
        ))
    fig.update_layout(
        title=f"{column} par {factor}",
        margin=dict(t=60, r=20, b=60, l=70),
        xaxis_title=factor, yaxis_title=column, showlegend=False,
    )
    return fig


def _grouped_box_figure(frame: pd.DataFrame, column: str, factor_a: str, factor_b: str) -> go.Figure:
    fig = go.Figure()
    for i, (level_b, group) in enumerate(frame.groupby(factor_b)):
        fig.add_trace(go.Box(
            y=group[column], x=group[factor_a], name=str(level_b),
            marker_color=DEFAULT_QUALITATIVE[i % len(DEFAULT_QUALITATIVE)], boxmean=True,
        ))
    fig.update_layout(
        boxmode="group",
        title=f"{column} par {factor_a} et {factor_b}",
        margin=dict(t=60, r=20, b=60, l=70),
        xaxis_title=factor_a, yaxis_title=column,
    )
    return fig


def _scatter_figure(x: np.ndarray, y: np.ndarray, name_x: str, name_y: str,
                    grid: np.ndarray, fitted: np.ndarray, r: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", name="observations",
        marker=dict(color=DEFAULT_QUALITATIVE[0], size=6, opacity=0.65),
        hovertemplate=f"{name_x} = %{{x:.4g}}<br>{name_y} = %{{y:.4g}}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=grid, y=fitted, mode="lines", name="droite d'ajustement",
        line=dict(color=DEFAULT_QUALITATIVE[3], width=2.5), hoverinfo="skip",
    ))
    fig.add_annotation(
        xref="paper", yref="paper", x=0.02, y=0.98, xanchor="left", yanchor="top",
        text=f"r = {r:.4f}", showarrow=False,
        bgcolor="rgba(255,255,255,0.75)", bordercolor=DEFAULT_QUALITATIVE[3], borderwidth=1, borderpad=4,
    )
    fig.update_layout(
        title=f"{name_y} en fonction de {name_x}",
        margin=dict(t=60, r=20, b=60, l=70),
        xaxis_title=name_x, yaxis_title=name_y,
    )
    return fig


def _fit_figure(values: np.ndarray, distribution, column: str, label: str, test: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=values, histnorm="probability density", name="observations",
        marker_color=DEFAULT_QUALITATIVE[0], opacity=0.65, nbinsx=40,
    ))
    try:
        params = distribution.fit(values)
        grid = np.linspace(float(values.min()), float(values.max()), 300)
        density = distribution.pdf(grid, *params)
        fig.add_trace(go.Scatter(
            x=grid, y=density, mode="lines", name=f"loi {label} ajustée",
            line=dict(color=DEFAULT_QUALITATIVE[3], width=2.5),
        ))
    except (ValueError, FloatingPointError, RuntimeError):
        pass
    fig.update_layout(
        title=f"Ajustement de {column} — {test.upper()}",
        margin=dict(t=60, r=20, b=60, l=70),
        xaxis_title=column, yaxis_title="Densité",
    )
    return fig


def _contingency_figure(table: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Heatmap(
        z=table.to_numpy(),
        x=[str(c) for c in table.columns],
        y=[str(i) for i in table.index],
        colorscale="Blues",
        text=table.to_numpy(),
        texttemplate="%{text}",
        hovertemplate="%{y} · %{x}<br>%{z} observation(s)<extra></extra>",
        colorbar=dict(title="Effectif", thickness=14),
    ))
    fig.update_layout(
        title="Table de contingence observée",
        margin=dict(t=60, r=20, b=90, l=110),
        xaxis=dict(tickangle=-40, automargin=True),
        yaxis=dict(automargin=True, autorange="reversed"),
    )
    return fig


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------

FAMILY_DISPATCH = {
    "hypothesis": _hypothesis_test,
    "anova": _anova,
    "correlation": _correlation_test,
    "goodness_of_fit": _goodness_of_fit,
}

TESTS_BY_FAMILY = {
    "hypothesis": {"ttest_ind", "ttest_rel", "ttest_1samp", "mannwhitney", "wilcoxon"},
    "anova": {"one_way", "two_way"},
    "correlation": {"pearson", "spearman", "kendall"},
    "goodness_of_fit": {"shapiro", "ks", "anderson", "chi2"},
}


def run_statistical_test(df: pd.DataFrame, req) -> dict[str, Any]:
    if req.test not in TESTS_BY_FAMILY[req.family]:
        raise AppError(
            400, "TEST_FAMILY_MISMATCH",
            f"Le test « {req.test} » n'appartient pas à la famille « {req.family} ». "
            f"Tests disponibles : {', '.join(sorted(TESTS_BY_FAMILY[req.family]))}.",
        )
    if not 0 < req.alpha < 1:
        raise AppError(400, "INVALID_ALPHA", "Le seuil α doit être strictement compris entre 0 et 1.")

    result = FAMILY_DISPATCH[req.family](df, req)
    result["family"] = req.family
    result["test"] = req.test
    result["alpha"] = req.alpha
    return result
