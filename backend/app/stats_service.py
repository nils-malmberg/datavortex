"""Statistiques avancées (Phase 8) : corrélations, distributions, données manquantes.

Complète `app.stats` (résumé simple par colonne) avec les analyses attendues
par un data scientist : matrice de corrélation avec p-values, tests de
normalité et ajustement de loi, intervalles de confiance, et cartographie des
valeurs manquantes accompagnée de suggestions d'imputation.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats as sps
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

from app.errors import AppError
from app.parsing import detect_column_type

# Bornes de sûreté : ces analyses sont O(n) à O(n²) et tournent en synchrone.
MAX_SHAPIRO_SAMPLE = 5000
MAX_MISSING_MATRIX_ROWS = 300
MAX_QQ_POINTS = 500
MAX_MISSING_PATTERNS = 12

NUMERIC_TYPES = ("integer", "float")


def _num(value: Any) -> Optional[float]:
    """Rend une valeur JSON-safe : NaN/inf deviennent None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if detect_column_type(df[c]) in NUMERIC_TYPES]


def _clean(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").dropna()


# --------------------------------------------------------------------------
# Résumé étendu (onglet "Summary")
# --------------------------------------------------------------------------

def extended_numeric_stats(series: pd.Series) -> dict[str, Any]:
    """Stats descriptives enrichies : CV, erreur standard, IQR et bornes outliers."""
    clean = pd.to_numeric(series, errors="coerce").dropna()
    n = int(clean.count())
    if n == 0:
        return {"count": 0}

    mean = float(clean.mean())
    std = float(clean.std()) if n > 1 else 0.0
    q1 = float(clean.quantile(0.25))
    q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    std_error = std / math.sqrt(n) if n > 0 else 0.0
    # Coefficient de variation : sans signification si la moyenne est ~0.
    cv = (std / abs(mean) * 100) if abs(mean) > 1e-12 else None
    mad = float((clean - clean.median()).abs().median())

    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr
    n_outliers = int(((clean < lower_fence) | (clean > upper_fence)).sum())

    return {
        "count": n,
        "mean": _num(mean),
        "median": _num(clean.median()),
        "std": _num(std),
        "variance": _num(clean.var()) if n > 1 else 0.0,
        "std_error": _num(std_error),
        "cv_percent": _num(cv),
        "min": _num(clean.min()),
        "q1": _num(q1),
        "q3": _num(q3),
        "max": _num(clean.max()),
        "iqr": _num(iqr),
        "mad": _num(mad),
        "range": _num(clean.max() - clean.min()),
        "sum": _num(clean.sum()),
        "p05": _num(clean.quantile(0.05)),
        "p95": _num(clean.quantile(0.95)),
        "lower_fence": _num(lower_fence),
        "upper_fence": _num(upper_fence),
        "outlier_count": n_outliers,
        "ci95": confidence_interval(clean, 0.95),
        "ci99": confidence_interval(clean, 0.99),
    }


def confidence_interval(clean: pd.Series, level: float) -> dict[str, Any]:
    """Intervalle de confiance de la moyenne (loi de Student, variance inconnue)."""
    n = int(clean.count())
    if n < 2:
        return {"level": level, "low": None, "high": None, "margin": None}
    mean = float(clean.mean())
    sem = float(clean.std()) / math.sqrt(n)
    t_crit = float(sps.t.ppf(0.5 + level / 2, df=n - 1))
    margin = t_crit * sem
    return {
        "level": level,
        "low": _num(mean - margin),
        "high": _num(mean + margin),
        "margin": _num(margin),
    }


# --------------------------------------------------------------------------
# Corrélations (onglet "Correlations")
# --------------------------------------------------------------------------

def correlation_analysis(df: pd.DataFrame, method: str = "pearson") -> dict[str, Any]:
    """Matrice de corrélation + p-values + ordre issu d'un clustering hiérarchique."""
    cols = numeric_columns(df)
    if len(cols) < 2:
        return {
            "columns": [], "matrix": [], "p_values": [], "n_pairs": [],
            "clustered_order": [], "method": method,
            "message": "Au moins 2 colonnes numériques sont nécessaires pour une matrice de corrélation.",
        }

    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    size = len(cols)
    matrix = np.full((size, size), np.nan)
    pvalues = np.full((size, size), np.nan)
    pair_counts = np.zeros((size, size), dtype=int)

    corr_fn = {"pearson": sps.pearsonr, "spearman": sps.spearmanr, "kendall": sps.kendalltau}.get(method)
    if corr_fn is None:
        raise AppError(400, "UNKNOWN_CORRELATION_METHOD", f"Méthode de corrélation inconnue : '{method}'.")

    for i in range(size):
        for j in range(i, size):
            # Suppression par paire : on garde le maximum d'information disponible.
            pair = sub[[cols[i], cols[j]]].dropna()
            n_pair = len(pair)
            pair_counts[i, j] = pair_counts[j, i] = n_pair
            if i == j:
                matrix[i, j] = 1.0
                pvalues[i, j] = 0.0
                continue
            if n_pair < 3 or pair[cols[i]].nunique() < 2 or pair[cols[j]].nunique() < 2:
                continue
            try:
                res = corr_fn(pair[cols[i]].to_numpy(), pair[cols[j]].to_numpy())
                r, p = float(res[0]), float(res[1])
            except (ValueError, FloatingPointError):
                continue
            matrix[i, j] = matrix[j, i] = r
            pvalues[i, j] = pvalues[j, i] = p

    return {
        "columns": cols,
        "matrix": [[_num(v) for v in row] for row in matrix],
        "p_values": [[_num(v) for v in row] for row in pvalues],
        "n_pairs": pair_counts.tolist(),
        "clustered_order": _hierarchical_order(matrix, cols),
        "method": method,
        "strongest": _strongest_pairs(matrix, pvalues, cols),
    }


def _hierarchical_order(matrix: np.ndarray, cols: list[str]) -> list[str]:
    """Réordonne les colonnes par clustering hiérarchique (distance = 1 - |r|).

    Regroupe visuellement les variables corrélées entre elles dans la heatmap.
    """
    if len(cols) < 3:
        return list(cols)
    filled = np.nan_to_num(matrix, nan=0.0)
    distance = 1.0 - np.abs(filled)
    np.fill_diagonal(distance, 0.0)
    # squareform exige une matrice parfaitement symétrique et positive.
    distance = np.clip((distance + distance.T) / 2, 0.0, 2.0)
    try:
        linkage = hierarchy.linkage(squareform(distance, checks=False), method="average")
        order = hierarchy.leaves_list(linkage)
    except (ValueError, FloatingPointError):
        return list(cols)
    return [cols[i] for i in order]


def _strongest_pairs(matrix: np.ndarray, pvalues: np.ndarray, cols: list[str], limit: int = 10) -> list[dict]:
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = matrix[i, j]
            if np.isnan(r):
                continue
            pairs.append({
                "x": cols[i], "y": cols[j],
                "r": _num(r), "p_value": _num(pvalues[i, j]),
                "significant": bool(pvalues[i, j] < 0.05) if not np.isnan(pvalues[i, j]) else False,
            })
    pairs.sort(key=lambda p: abs(p["r"] or 0), reverse=True)
    return pairs[:limit]


# --------------------------------------------------------------------------
# Distributions (onglet "Distributions")
# --------------------------------------------------------------------------

def _interpret_skewness(skew: float) -> str:
    a = abs(skew)
    side = "à droite" if skew > 0 else "à gauche"
    if a < 0.5:
        return "Distribution approximativement symétrique"
    if a < 1.0:
        return f"Distribution légèrement asymétrique {side}"
    return f"Distribution fortement asymétrique {side}"


def _interpret_kurtosis(kurt: float) -> str:
    """`kurt` est l'excès de kurtosis (0 = normale)."""
    if abs(kurt) < 0.5:
        return "Aplatissement proche de la normale (mésokurtique)"
    if kurt >= 0.5:
        return "Pic marqué et queues épaisses (leptokurtique) — valeurs extrêmes plus fréquentes"
    return "Distribution aplatie, queues fines (platykurtique)"


CANDIDATE_LAWS = ("normal", "lognormal", "exponential", "uniform", "gamma")


def _fit_candidate(clean: np.ndarray, law: str) -> Optional[dict]:
    """Ajuste une loi par maximum de vraisemblance, avec test KS et AIC.

    Deux indicateurs distincts et complémentaires :
    - le test de Kolmogorov-Smirnov dit si la loi est *acceptable* (ses p-values,
      calculées avec des paramètres estimés sur l'échantillon, sont optimistes :
      elles servent de garde-fou, pas de validation formelle) ;
    - l'AIC dit laquelle *choisir* parmi les lois acceptables, en pénalisant les
      paramètres libres. Sans cette pénalité, une loi gamma (2 paramètres)
      l'emporterait systématiquement sur l'exponentielle qu'elle contient
      comme cas particulier.
    """
    try:
        if law == "normal":
            dist, params, n_free = sps.norm, sps.norm.fit(clean), 2
        elif law == "lognormal":
            if np.any(clean <= 0):
                return None
            dist, params, n_free = sps.lognorm, sps.lognorm.fit(clean, floc=0), 2
        elif law == "exponential":
            if np.any(clean < 0):
                return None
            # loc fixé à 0 : une loi exponentielle démarre à l'origine.
            dist, params, n_free = sps.expon, sps.expon.fit(clean, floc=0), 1
        elif law == "uniform":
            dist, params, n_free = sps.uniform, sps.uniform.fit(clean), 2
        elif law == "gamma":
            if np.any(clean <= 0):
                return None
            dist, params, n_free = sps.gamma, sps.gamma.fit(clean, floc=0), 2
        else:  # pragma: no cover - liste fermée
            return None
        ks_stat, ks_p = sps.kstest(clean, dist.cdf, args=params)
        log_likelihood = float(np.sum(dist.logpdf(clean, *params)))
        aic = 2 * n_free - 2 * log_likelihood
    except (ValueError, FloatingPointError, RuntimeError):
        return None
    if not np.isfinite(aic):
        return None
    return {
        "law": law,
        "ks_statistic": _num(ks_stat),
        "p_value": _num(ks_p),
        "aic": _num(aic),
        "n_params": n_free,
        "params": [_num(p) for p in params],
    }


def _fit_is_acceptable(fit: Optional[dict]) -> bool:
    """Un ajustement n'est retenu que si le test KS ne le rejette pas (p > 0.05)."""
    return bool(fit and fit.get("p_value") is not None and fit["p_value"] > 0.05)


# Convention de Burnham & Anderson : deux modèles séparés par moins de 2 points
# d'AIC ne sont pas distinguables par les données.
AIC_INDIFFERENCE = 2.0


def _select_best_fit(fits: list[dict]) -> Optional[dict]:
    """Retient la loi la plus simple parmi celles que l'AIC ne départage pas.

    Sans cette règle, une gamma battrait toujours de peu l'exponentielle qu'elle
    généralise, et l'utilisateur verrait « gamma » sur des données franchement
    exponentielles.
    """
    if not fits:
        return None
    best_aic = min(f["aic"] for f in fits)
    equivalent = [f for f in fits if f["aic"] <= best_aic + AIC_INDIFFERENCE]
    return min(equivalent, key=lambda f: (f["n_params"], f["aic"]))


def distribution_analysis(df: pd.DataFrame, columns: Optional[list[str]] = None) -> dict[str, Any]:
    cols = columns or numeric_columns(df)
    out: dict[str, Any] = {}

    for col in cols:
        clean = _clean(df, col)
        n = int(clean.size)
        if n < 3 or clean.nunique() < 2:
            out[col] = {
                "count": n,
                "usable": False,
                "message": "Pas assez de valeurs distinctes pour analyser la distribution.",
            }
            continue

        values = clean.to_numpy(dtype=float)
        skew = float(sps.skew(values))
        kurt = float(sps.kurtosis(values))  # excès de kurtosis (Fisher)

        normality = _normality_tests(values)
        fits = [f for f in (_fit_candidate(values, law) for law in CANDIDATE_LAWS) if f]
        # Classement par AIC (le plus petit gagne) ; le test KS filtre ensuite
        # les ajustements qui, même « meilleurs », restent inacceptables.
        fits.sort(key=lambda f: f["aic"] if f["aic"] is not None else float("inf"))
        acceptable = [f for f in fits if _fit_is_acceptable(f)]
        best = _select_best_fit(acceptable) or (fits[0] if fits else None)

        out[col] = {
            "count": n,
            "usable": True,
            "skewness": _num(skew),
            "skewness_interpretation": _interpret_skewness(skew),
            "kurtosis": _num(kurt),
            "kurtosis_interpretation": _interpret_kurtosis(kurt),
            "normality": normality,
            "is_normal": bool(normality["verdict"] == "normal"),
            "fits": fits,
            "best_fit": best,
            # On ne nomme une loi que si l'ajustement tient réellement (KS non rejeté) :
            # annoncer "normale" pour une distribution bimodale serait trompeur.
            "detected_law": best["law"] if _fit_is_acceptable(best) else None,
            "fit_message": (
                None if _fit_is_acceptable(best)
                else "Aucune loi usuelle (normale, log-normale, exponentielle, uniforme, gamma) "
                     "n'ajuste correctement cette distribution."
            ),
            "qq_plot": _qq_points(values),
            "ci95": confidence_interval(clean, 0.95),
            "ci99": confidence_interval(clean, 0.99),
        }

    return out


def _normality_tests(values: np.ndarray) -> dict[str, Any]:
    n = values.size
    tests: dict[str, Any] = {}

    if 3 <= n <= MAX_SHAPIRO_SAMPLE:
        sample = values
    elif n > MAX_SHAPIRO_SAMPLE:
        rng = np.random.default_rng(42)
        sample = rng.choice(values, size=MAX_SHAPIRO_SAMPLE, replace=False)
    else:
        sample = values

    try:
        stat, p = sps.shapiro(sample)
        tests["shapiro"] = {
            "statistic": _num(stat), "p_value": _num(p),
            "sampled": bool(n > MAX_SHAPIRO_SAMPLE), "n_used": int(sample.size),
        }
    except (ValueError, FloatingPointError):
        tests["shapiro"] = None

    if n >= 20:
        try:
            stat, p = sps.normaltest(values)
            tests["dagostino"] = {"statistic": _num(stat), "p_value": _num(p)}
        except (ValueError, FloatingPointError):
            tests["dagostino"] = None
    else:
        tests["dagostino"] = None

    try:
        result = sps.anderson(values, dist="norm")
        # Le seuil 5% est en position 2 des niveaux [15, 10, 5, 2.5, 1].
        crit_5pct = float(result.critical_values[2])
        tests["anderson"] = {
            "statistic": _num(result.statistic),
            "critical_value_5pct": _num(crit_5pct),
            "normal_at_5pct": bool(result.statistic < crit_5pct),
        }
    except (ValueError, FloatingPointError):
        tests["anderson"] = None

    # Verdict : on privilégie Shapiro-Wilk (le plus puissant sur petits échantillons).
    primary = tests.get("shapiro") or tests.get("dagostino")
    if primary and primary.get("p_value") is not None:
        is_normal = primary["p_value"] > 0.05
        verdict = "normal" if is_normal else "non_normal"
        interpretation = (
            f"p = {primary['p_value']:.4g} > 0.05 : l'hypothèse de normalité n'est pas rejetée."
            if is_normal
            else f"p = {primary['p_value']:.4g} ≤ 0.05 : la normalité est rejetée."
        )
    else:
        verdict, interpretation = "unknown", "Tests de normalité indisponibles pour cette colonne."

    tests["verdict"] = verdict
    tests["interpretation"] = interpretation
    return tests


def _qq_points(values: np.ndarray) -> dict[str, Any]:
    """Points d'un Q-Q plot contre la loi normale, sous-échantillonnés si besoin."""
    try:
        (theoretical, sample), (slope, intercept, r) = sps.probplot(values, dist="norm")
    except (ValueError, FloatingPointError):
        return {"theoretical": [], "sample": [], "slope": None, "intercept": None}

    if theoretical.size > MAX_QQ_POINTS:
        idx = np.linspace(0, theoretical.size - 1, MAX_QQ_POINTS).astype(int)
        theoretical, sample = theoretical[idx], sample[idx]

    return {
        "theoretical": [_num(v) for v in theoretical],
        "sample": [_num(v) for v in sample],
        "slope": _num(slope),
        "intercept": _num(intercept),
        "r": _num(r),
    }


# --------------------------------------------------------------------------
# Données manquantes (onglet "Missing Data")
# --------------------------------------------------------------------------

def _suggest_imputation(df: pd.DataFrame, col: str, missing_pct: float) -> dict[str, Any]:
    col_type = detect_column_type(df[col])

    if missing_pct == 0:
        return {"method": "none", "label": "Aucune action", "reason": "Colonne complète."}
    if missing_pct > 60:
        return {
            "method": "drop_column", "label": "Supprimer la colonne",
            "reason": f"{missing_pct:.1f}% de valeurs manquantes : imputer introduirait plus de bruit que de signal.",
        }

    if col_type in NUMERIC_TYPES:
        clean = _clean(df, col)
        skew = float(sps.skew(clean.to_numpy(dtype=float))) if clean.size >= 3 else 0.0
        if abs(skew) > 1.0:
            return {
                "method": "median", "label": "Imputer par la médiane",
                "reason": f"Distribution asymétrique (skew = {skew:.2f}) : la médiane résiste mieux aux valeurs extrêmes.",
            }
        return {
            "method": "mean", "label": "Imputer par la moyenne",
            "reason": f"Distribution approximativement symétrique (skew = {skew:.2f}) : la moyenne est un estimateur adapté.",
        }

    if col_type == "datetime":
        return {
            "method": "interpolate", "label": "Interpoler / propager",
            "reason": "Colonne temporelle : une interpolation respecte l'ordre chronologique.",
        }

    nunique = int(df[col].dropna().nunique())
    if nunique <= 20:
        return {
            "method": "mode", "label": "Imputer par le mode",
            "reason": f"Catégorielle à faible cardinalité ({nunique} modalités) : la modalité la plus fréquente est un choix sûr.",
        }
    return {
        "method": "constant", "label": "Remplacer par 'Inconnu'",
        "reason": f"Catégorielle à forte cardinalité ({nunique} modalités) : marquer explicitement l'absence évite d'inventer une modalité.",
    }


def missing_analysis(df: pd.DataFrame) -> dict[str, Any]:
    n_rows = int(df.shape[0])
    na_mask = df.isna()

    by_column = []
    for col in df.columns:
        count = int(na_mask[col].sum())
        pct = round((count / n_rows) * 100, 2) if n_rows else 0.0
        by_column.append({
            "column": str(col),
            "missing_count": count,
            "missing_pct": pct,
            "present_count": n_rows - count,
            "type": detect_column_type(df[col]),
            "suggestion": _suggest_imputation(df, col, pct),
        })

    affected = [c["column"] for c in by_column if c["missing_count"] > 0]

    # Patterns : combinaisons distinctes de colonnes manquantes sur une ligne.
    patterns: list[dict] = []
    if affected:
        sub = na_mask[affected]
        grouped = sub.groupby(list(affected)).size().reset_index(name="count")
        grouped = grouped.sort_values("count", ascending=False).head(MAX_MISSING_PATTERNS)
        for _, row in grouped.iterrows():
            missing_cols = [c for c in affected if bool(row[c])]
            patterns.append({
                "columns_missing": missing_cols,
                "count": int(row["count"]),
                "pct": round((int(row["count"]) / n_rows) * 100, 2) if n_rows else 0.0,
                "is_complete": len(missing_cols) == 0,
            })

    # Heatmap : sous-échantillon régulier des lignes pour rester lisible et léger.
    matrix_cols = affected or [str(c) for c in df.columns][:20]
    if n_rows > MAX_MISSING_MATRIX_ROWS:
        idx = np.linspace(0, n_rows - 1, MAX_MISSING_MATRIX_ROWS).astype(int)
        matrix_source = na_mask.iloc[idx][matrix_cols]
        row_labels = [int(df.index[i]) if isinstance(df.index[i], (int, np.integer)) else i for i in idx]
    else:
        matrix_source = na_mask[matrix_cols]
        row_labels = list(range(n_rows))

    total_cells = n_rows * int(df.shape[1])
    total_missing = int(na_mask.to_numpy().sum())

    return {
        "n_rows": n_rows,
        "n_columns": int(df.shape[1]),
        "total_missing": total_missing,
        "total_missing_pct": round((total_missing / total_cells) * 100, 2) if total_cells else 0.0,
        "complete_rows": int((~na_mask.any(axis=1)).sum()),
        "columns_with_missing": len(affected),
        "by_column": by_column,
        "patterns": patterns,
        "matrix": {
            "columns": [str(c) for c in matrix_cols],
            "rows": matrix_source.astype(int).to_numpy().tolist(),
            "row_labels": row_labels,
            "sampled": bool(n_rows > MAX_MISSING_MATRIX_ROWS),
        },
    }


# --------------------------------------------------------------------------
# Point d'entrée agrégé
# --------------------------------------------------------------------------

def advanced_stats(df: pd.DataFrame, correlation_method: str = "pearson") -> dict[str, Any]:
    num_cols = numeric_columns(df)
    return {
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "numeric_columns": num_cols,
        "categorical_columns": [str(c) for c in df.columns if c not in num_cols],
        "summary": {col: extended_numeric_stats(df[col]) for col in num_cols},
        "correlations": correlation_analysis(df, correlation_method),
        "distributions": distribution_analysis(df, num_cols),
        "missing": missing_analysis(df),
    }


# --------------------------------------------------------------------------
# Export tabulaire des statistiques (CSV / Excel / LaTeX)
# --------------------------------------------------------------------------

EXPORTABLE_TABLES = ("summary", "correlations", "distributions", "missing")


def stats_export_table(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Met à plat une des analyses en un DataFrame prêt à exporter."""
    if table == "summary":
        rows = []
        for col in numeric_columns(df):
            stats = extended_numeric_stats(df[col])
            rows.append({
                "Colonne": col,
                "N": stats.get("count"),
                "Moyenne": stats.get("mean"),
                "Médiane": stats.get("median"),
                "Écart-type": stats.get("std"),
                "Erreur standard": stats.get("std_error"),
                "CV (%)": stats.get("cv_percent"),
                "Min": stats.get("min"),
                "Q1": stats.get("q1"),
                "Q3": stats.get("q3"),
                "Max": stats.get("max"),
                "IQR": stats.get("iqr"),
                "MAD": stats.get("mad"),
                "IC 95% bas": (stats.get("ci95") or {}).get("low"),
                "IC 95% haut": (stats.get("ci95") or {}).get("high"),
                "Outliers (IQR)": stats.get("outlier_count"),
            })
        if not rows:
            raise AppError(422, "NO_NUMERIC_COLUMNS", "Aucune colonne numérique à exporter.")
        return pd.DataFrame(rows)

    if table == "correlations":
        analysis = correlation_analysis(df)
        if not analysis["columns"]:
            raise AppError(422, "INSUFFICIENT_COLUMNS", analysis.get("message", "Corrélations indisponibles."))
        matrix = pd.DataFrame(analysis["matrix"], index=analysis["columns"], columns=analysis["columns"])
        return matrix.reset_index().rename(columns={"index": "Colonne"})

    if table == "distributions":
        rows = []
        for col, info in distribution_analysis(df).items():
            if not info.get("usable"):
                continue
            normality = info.get("normality") or {}
            shapiro = normality.get("shapiro") or {}
            rows.append({
                "Colonne": col,
                "N": info.get("count"),
                "Asymétrie": info.get("skewness"),
                "Interprétation asymétrie": info.get("skewness_interpretation"),
                "Kurtosis": info.get("kurtosis"),
                "Interprétation kurtosis": info.get("kurtosis_interpretation"),
                "Shapiro p-value": shapiro.get("p_value"),
                "Normale (5%)": "oui" if info.get("is_normal") else "non",
                "Loi ajustée": info.get("detected_law"),
            })
        if not rows:
            raise AppError(422, "NO_NUMERIC_COLUMNS", "Aucune distribution exploitable à exporter.")
        return pd.DataFrame(rows)

    if table == "missing":
        analysis = missing_analysis(df)
        return pd.DataFrame([
            {
                "Colonne": item["column"],
                "Type": item["type"],
                "Manquantes": item["missing_count"],
                "Manquantes (%)": item["missing_pct"],
                "Présentes": item["present_count"],
                "Imputation suggérée": item["suggestion"]["label"],
                "Justification": item["suggestion"]["reason"],
            }
            for item in analysis["by_column"]
        ])

    raise AppError(400, "UNKNOWN_STATS_TABLE", f"Table de statistiques inconnue : '{table}'.")
