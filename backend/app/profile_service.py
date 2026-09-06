"""Profilage détaillé d'un jeu de données (Phase 8).

Répond à la question qu'on se pose avant toute analyse : « à quel point puis-je
faire confiance à ces données ? ». Chaque indicateur de qualité est défini
explicitement et renvoyé avec sa définition, pour qu'un score de 82/100 puisse
être interprété plutôt que cru sur parole.
"""
from __future__ import annotations

import difflib
import math
import re
import unicodedata
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats as sps
from sklearn.ensemble import IsolationForest

from app.parsing import detect_column_type
from app.stats_service import missing_analysis

NUMERIC_TYPES = ("integer", "float")

MAX_FUZZY_DISTINCT = 300
MAX_ISOLATION_ROWS = 20_000
MAX_OUTLIER_EXAMPLES = 10
FUZZY_SIMILARITY = 0.86

# Chaînes qui signalent une donnée absente sans être un vrai NaN : elles passent
# les contrôles de type mais ne portent aucune information.
SENTINEL_VALUES = {
    "", "-", "--", "?", "??", "n/a", "na", "n.a.", "none", "null", "nil", "nan",
    "#n/a", "#na", "unknown", "inconnu", "non renseigné", "non renseigne", ".",
}
SENTINEL_NUMBERS = {-999, -9999, -99999, 999999}


def _num(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else f


def _normalize_text(value: str) -> str:
    """Forme canonique d'un libellé : sert à repérer les variantes d'écriture."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().casefold()


# --------------------------------------------------------------------------
# Onglet « Profil »
# --------------------------------------------------------------------------

def _shape_label(skew: float, kurt: float) -> str:
    parts = []
    if abs(skew) < 0.5:
        parts.append("symétrique")
    elif skew > 0:
        parts.append("étalée vers la droite")
    else:
        parts.append("étalée vers la gauche")
    if kurt > 1:
        parts.append("queues épaisses")
    elif kurt < -1:
        parts.append("aplatie")
    return ", ".join(parts)


def column_profile(series: pd.Series) -> dict[str, Any]:
    col_type = detect_column_type(series)
    n_total = int(series.size)
    n_missing = int(series.isna().sum())
    n_present = n_total - n_missing
    n_unique = int(series.nunique(dropna=True))

    profile: dict[str, Any] = {
        "type": col_type,
        "count": n_present,
        "missing": n_missing,
        "missing_pct": round(n_missing / n_total * 100, 2) if n_total else 0.0,
        "unique": n_unique,
        "unique_pct": round(n_unique / n_present * 100, 2) if n_present else 0.0,
        # Une colonne dont chaque valeur est unique est presque toujours une clé.
        "is_probable_key": bool(n_present > 0 and n_unique == n_present and n_present > 1),
        "is_constant": bool(n_unique <= 1 and n_present > 0),
    }

    non_null = series.dropna()
    if not non_null.empty:
        counts = non_null.astype(str).value_counts()
        profile["mode"] = counts.index[0]
        profile["mode_count"] = int(counts.iloc[0])
        profile["top_values"] = [{"value": v, "count": int(c)} for v, c in counts.head(8).items()]
    else:
        profile["mode"] = None
        profile["mode_count"] = 0
        profile["top_values"] = []

    if col_type in NUMERIC_TYPES:
        clean = pd.to_numeric(series, errors="coerce").dropna()
        if clean.size >= 1:
            values = clean.to_numpy(dtype=float)
            skew = float(sps.skew(values)) if clean.size >= 3 else 0.0
            kurt = float(sps.kurtosis(values)) if clean.size >= 4 else 0.0
            profile.update({
                "mean": _num(clean.mean()),
                "median": _num(clean.median()),
                "std": _num(clean.std()) if clean.size > 1 else 0.0,
                "min": _num(clean.min()),
                "max": _num(clean.max()),
                "range": _num(clean.max() - clean.min()),
                "q1": _num(clean.quantile(0.25)),
                "q3": _num(clean.quantile(0.75)),
                "skewness": _num(skew),
                "kurtosis": _num(kurt),
                "shape": _shape_label(skew, kurt),
                "zeros": int((clean == 0).sum()),
                "negatives": int((clean < 0).sum()),
            })
    elif col_type == "string":
        lengths = non_null.astype(str).str.len()
        if not lengths.empty:
            profile.update({
                "min_length": int(lengths.min()),
                "max_length": int(lengths.max()),
                "mean_length": _num(lengths.mean()),
                "empty_strings": int((non_null.astype(str).str.strip() == "").sum()),
            })

    return profile


# --------------------------------------------------------------------------
# Onglet « Qualité »
# --------------------------------------------------------------------------

def _type_mismatches(series: pd.Series, col_type: str) -> int:
    """Valeurs non nulles incompatibles avec le type détecté de la colonne."""
    non_null = series.dropna()
    if non_null.empty:
        return 0
    if col_type in NUMERIC_TYPES:
        return int(pd.to_numeric(non_null, errors="coerce").isna().sum())
    if col_type == "datetime":
        return int(pd.to_datetime(non_null, errors="coerce").isna().sum())
    if col_type == "boolean":
        allowed = {"true", "false", "1", "0", "yes", "no", "oui", "non"}
        return int((~non_null.astype(str).str.strip().str.lower().isin(allowed)).sum())
    return 0


def _sentinel_count(series: pd.Series, col_type: str) -> int:
    non_null = series.dropna()
    if non_null.empty:
        return 0
    if col_type in NUMERIC_TYPES:
        numeric = pd.to_numeric(non_null, errors="coerce")
        return int(numeric.isin(list(SENTINEL_NUMBERS)).sum())
    return int(non_null.astype(str).str.strip().str.lower().isin(SENTINEL_VALUES).sum())


def _inconsistent_formatting(series: pd.Series, col_type: str) -> int:
    """Valeurs textuelles qui ne diffèrent que par la casse ou les espaces."""
    if col_type != "string":
        return 0
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return 0
    normalized = non_null.map(_normalize_text)
    # Pour chaque forme canonique, tout ce qui n'est pas l'écriture majoritaire.
    frame = pd.DataFrame({"raw": non_null, "norm": normalized})
    inconsistent = 0
    for _, group in frame.groupby("norm"):
        variants = group["raw"].value_counts()
        if variants.size > 1:
            inconsistent += int(variants.iloc[1:].sum())
    return inconsistent


def quality_report(df: pd.DataFrame) -> dict[str, Any]:
    n_rows, n_cols = int(df.shape[0]), int(df.shape[1])
    total_cells = n_rows * n_cols

    missing_cells = int(df.isna().to_numpy().sum())
    duplicate_rows = int(df.duplicated().sum())
    mismatches = 0
    sentinels = 0
    inconsistent = 0
    extreme = 0
    numeric_cells = 0

    per_column = []
    for col in df.columns:
        col_type = detect_column_type(df[col])
        col_mismatch = _type_mismatches(df[col], col_type)
        col_sentinel = _sentinel_count(df[col], col_type)
        col_inconsistent = _inconsistent_formatting(df[col], col_type)
        col_extreme = 0
        if col_type in NUMERIC_TYPES:
            clean = pd.to_numeric(df[col], errors="coerce").dropna()
            numeric_cells += int(clean.size)
            if clean.size >= 4:
                q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    # Seuil « extrême » de Tukey (3·IQR), pas le simple 1,5·IQR :
                    # une valeur au-delà est le plus souvent une erreur de saisie.
                    col_extreme = int(((clean < q1 - 3 * iqr) | (clean > q3 + 3 * iqr)).sum())

        mismatches += col_mismatch
        sentinels += col_sentinel
        inconsistent += col_inconsistent
        extreme += col_extreme

        per_column.append({
            "column": str(col),
            "type": col_type,
            "missing": int(df[col].isna().sum()),
            "type_mismatches": col_mismatch,
            "sentinel_values": col_sentinel,
            "inconsistent_formatting": col_inconsistent,
            "extreme_values": col_extreme,
        })

    def pct(good: int, total: int) -> float:
        return round(good / total * 100, 2) if total else 100.0

    text_cells = int(sum(
        df[c].notna().sum() for c in df.columns if detect_column_type(df[c]) == "string"
    ))

    dimensions = {
        "completeness": {
            "score": pct(total_cells - missing_cells, total_cells),
            "label": "Complétude",
            "definition": "Part des cellules effectivement renseignées.",
            "detail": f"{missing_cells} cellule(s) manquante(s) sur {total_cells}.",
        },
        "uniqueness": {
            "score": pct(n_rows - duplicate_rows, n_rows),
            "label": "Unicité",
            "definition": "Part des lignes qui ne sont pas des doublons exacts d'une ligne précédente.",
            "detail": f"{duplicate_rows} ligne(s) dupliquée(s) sur {n_rows}.",
        },
        "validity": {
            "score": pct(total_cells - missing_cells - mismatches - sentinels,
                         max(1, total_cells - missing_cells)),
            "label": "Validité",
            "definition": "Part des valeurs renseignées compatibles avec le type de leur colonne "
                          "et qui ne sont pas des marqueurs d'absence déguisés (« N/A », « -999 »…).",
            "detail": f"{mismatches} valeur(s) du mauvais type, {sentinels} marqueur(s) d'absence.",
        },
        "consistency": {
            "score": pct(text_cells - inconsistent, max(1, text_cells)),
            "label": "Cohérence",
            "definition": "Part des libellés textuels écrits sous leur forme majoritaire "
                          "(mêmes casse, accents et espaces que les autres occurrences).",
            "detail": f"{inconsistent} libellé(s) en variante d'écriture."
                      if text_cells else "Aucune colonne textuelle à comparer.",
        },
        "plausibility": {
            "score": pct(numeric_cells - extreme, max(1, numeric_cells)),
            "label": "Plausibilité",
            "definition": "Part des valeurs numériques situées dans les bornes extrêmes de Tukey "
                          "(au-delà de 3·IQR). Un écart signale une valeur à vérifier, "
                          "pas nécessairement une erreur.",
            "detail": f"{extreme} valeur(s) numérique(s) très éloignée(s) du reste."
                      if numeric_cells else "Aucune colonne numérique à évaluer.",
        },
    }

    overall = round(sum(d["score"] for d in dimensions.values()) / len(dimensions), 1)
    weakest_key = min(dimensions, key=lambda k: dimensions[k]["score"])
    weakest = dimensions[weakest_key]

    # Un défaut concentré sur peu de cellules reste un défaut : on compte aussi
    # combien de colonnes sont touchées, sinon un score de 97 % laisserait croire
    # qu'un jeu de données truffé de doublons et de variantes d'écriture est sain.
    columns_with_issues = [
        c["column"] for c in per_column
        if c["missing"] or c["type_mismatches"] or c["sentinel_values"]
        or c["inconsistent_formatting"] or c["extreme_values"]
    ]

    return {
        # Part de cellules saines, moyenne des cinq dimensions. C'est une mesure
        # au niveau cellule : elle ne dit pas combien de problèmes distincts existent.
        "score": overall,
        "score_definition": "Moyenne des cinq dimensions, chacune exprimée en part de cellules conformes. "
                            "Un score élevé signifie « peu de cellules fautives », pas « aucun problème ».",
        # La mention qualitative suit la dimension la plus faible : la qualité d'un
        # jeu de données est limitée par son maillon faible, pas par sa moyenne.
        "grade": _grade(weakest["score"]),
        "grade_basis": weakest["label"],
        "grade_definition": f"Établie sur la dimension la plus faible ({weakest['label']} : "
                            f"{weakest['score']} %), et non sur la moyenne.",
        "weakest_dimension": weakest_key,
        "dimensions": dimensions,
        "per_column": per_column,
        "columns_with_issues": columns_with_issues,
        "n_columns_with_issues": len(columns_with_issues),
        "n_rows": n_rows,
        "n_columns": n_cols,
    }


def _grade(score: float) -> str:
    """Mention qualitative attachée à une dimension.

    Les seuils sont serrés volontairement : sur un tableau de plusieurs milliers
    de cellules, 2 % de valeurs fautives représentent déjà des dizaines de
    corrections à faire avant toute analyse sérieuse.
    """
    if score >= 99.5:
        return "excellent"
    if score >= 98:
        return "bon"
    if score >= 95:
        return "correct"
    if score >= 85:
        return "fragile"
    return "problématique"


def duplicate_report(df: pd.DataFrame) -> dict[str, Any]:
    """Doublons exacts de lignes, et variantes d'écriture par colonne textuelle."""
    duplicated_mask = df.duplicated(keep=False)
    n_duplicate_rows = int(df.duplicated().sum())

    examples = []
    if n_duplicate_rows:
        sample = df[duplicated_mask].head(20)
        examples = [
            {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()}
            for row in sample.to_dict(orient="records")
        ]

    fuzzy_groups = []
    for col in df.columns:
        if detect_column_type(df[col]) != "string":
            continue
        values = df[col].dropna().astype(str)
        counts = values.value_counts()
        if counts.size < 2 or counts.size > MAX_FUZZY_DISTINCT:
            continue
        fuzzy_groups.extend(_fuzzy_variants(str(col), counts))

    return {
        "duplicate_rows": n_duplicate_rows,
        "duplicate_rows_pct": round(n_duplicate_rows / df.shape[0] * 100, 2) if df.shape[0] else 0.0,
        "rows_involved": int(duplicated_mask.sum()),
        "examples": examples,
        "fuzzy_groups": fuzzy_groups[:40],
        "fuzzy_limit_reached": any(
            df[c].dropna().nunique() > MAX_FUZZY_DISTINCT
            for c in df.columns if detect_column_type(df[c]) == "string"
        ),
    }


def _fuzzy_variants(column: str, counts: pd.Series) -> list[dict]:
    """Regroupe les libellés proches : même forme canonique, ou très similaires.

    Deux passes complémentaires : la normalisation attrape « Paris » / « paris »
    / « PARIS  », la similarité de séquence attrape « Marseille » / « Marseile ».
    """
    groups: list[dict] = []
    labels = list(counts.index)

    # Passe 1 : formes canoniques identiques.
    by_normal: dict[str, list[str]] = {}
    for label in labels:
        by_normal.setdefault(_normalize_text(label), []).append(label)
    grouped_labels = set()
    for normal, variants in by_normal.items():
        if len(variants) > 1:
            grouped_labels.update(variants)
            groups.append({
                "column": column,
                "kind": "casse_ou_espaces",
                "canonical": max(variants, key=lambda v: counts[v]),
                "variants": [{"value": v, "count": int(counts[v])} for v in variants],
            })

    # Passe 2 : similarité de séquence sur ce qui reste.
    remaining = [label for label in labels if label not in grouped_labels]
    seen: set[str] = set()
    for i, label in enumerate(remaining):
        if label in seen:
            continue
        candidates = [other for other in remaining[i + 1:] if other not in seen]
        close = difflib.get_close_matches(label, candidates, n=5, cutoff=FUZZY_SIMILARITY)
        if not close:
            continue
        members = [label, *close]
        seen.update(members)
        groups.append({
            "column": column,
            "kind": "orthographe_proche",
            "canonical": max(members, key=lambda v: counts[v]),
            "variants": [{"value": v, "count": int(counts[v])} for v in members],
        })

    return groups


# --------------------------------------------------------------------------
# Onglet « Anomalies »
# --------------------------------------------------------------------------

def anomaly_report(df: pd.DataFrame) -> dict[str, Any]:
    per_column = []
    for col in df.columns:
        col_type = detect_column_type(df[col])
        entry: dict[str, Any] = {"column": str(col), "type": col_type}

        mismatches = _type_mismatches(df[col], col_type)
        if mismatches:
            bad = df[col].dropna()
            if col_type in NUMERIC_TYPES:
                bad = bad[pd.to_numeric(bad, errors="coerce").isna()]
            elif col_type == "datetime":
                bad = bad[pd.to_datetime(bad, errors="coerce").isna()]
            entry["type_mismatch_count"] = mismatches
            entry["type_mismatch_examples"] = [str(v) for v in bad.head(5)]

        sentinels = _sentinel_count(df[col], col_type)
        if sentinels:
            entry["sentinel_count"] = sentinels

        if col_type in NUMERIC_TYPES:
            clean = pd.to_numeric(df[col], errors="coerce").dropna()
            if clean.size >= 4:
                entry["outliers"] = _numeric_outliers(clean)
        per_column.append(entry)

    return {
        "per_column": per_column,
        "multivariate": _isolation_forest(df),
    }


def _robust_bounds(clean: pd.Series) -> tuple[Optional[float], Optional[float], str]:
    """Bornes au-delà desquelles une valeur est jugée extrême.

    Deux règles en cascade, car la première dégénère sur les distributions très
    concentrées : quand plus de la moitié des valeurs sont identiques, l'écart
    interquartile vaut 0 et la règle de Tukey ne signale plus rien — y compris
    des valeurs manifestement aberrantes.
    """
    q1, q3 = clean.quantile(0.25), clean.quantile(0.75)
    iqr = q3 - q1
    if iqr > 0:
        return float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr), "iqr"

    # Un IQR nul impose un MAD nul : les deux exigent que la moitié centrale des
    # valeurs soit constante. Le repli robuste habituel est donc inutilisable ici,
    # et seul l'écart-type reste sensible aux valeurs extrêmes.
    std = clean.std()
    if std and std > 0:
        return float(clean.mean() - 3 * std), float(clean.mean() + 3 * std), "zscore"

    return None, None, "constant"


OUTLIER_RULE_LABELS = {
    "iqr": "règle de Tukey (Q1 − 1,5·IQR ; Q3 + 1,5·IQR)",
    "zscore": "moyenne ± 3σ — l'écart interquartile est nul, la règle de Tukey ne signalerait rien",
    "constant": "aucune : la colonne est constante",
}


def _numeric_outliers(clean: pd.Series) -> dict[str, Any]:
    lower, upper, rule = _robust_bounds(clean)
    robust_mask = ((clean < lower) | (clean > upper)) if lower is not None else clean != clean

    std = clean.std()
    z_mask = (((clean - clean.mean()).abs() / std) > 3) if std and std > 0 else clean != clean

    extremes = clean[robust_mask]
    examples = extremes.reindex((extremes - clean.median()).abs().sort_values(ascending=False).index)
    examples = examples.head(MAX_OUTLIER_EXAMPLES)

    return {
        "iqr_count": int(robust_mask.sum()),
        "iqr_pct": round(int(robust_mask.sum()) / clean.size * 100, 2),
        "zscore_count": int(z_mask.sum()),
        "zscore_pct": round(int(z_mask.sum()) / clean.size * 100, 2),
        "rule": rule,
        "rule_label": OUTLIER_RULE_LABELS[rule],
        "lower_fence": _num(lower),
        "upper_fence": _num(upper),
        "examples": [_num(v) for v in examples],
    }


def _isolation_forest(df: pd.DataFrame) -> dict[str, Any]:
    """Détection multivariée : des lignes atypiques par la *combinaison* de leurs
    valeurs, alors que chaque valeur prise isolément paraît normale."""
    numeric_cols = [c for c in df.columns if detect_column_type(df[c]) in NUMERIC_TYPES]
    if len(numeric_cols) < 2:
        return {
            "available": False,
            "reason": "Au moins 2 colonnes numériques sont nécessaires pour une détection multivariée.",
        }

    data = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    complete = data.dropna()
    if complete.shape[0] < 20:
        return {"available": False, "reason": "Trop peu de lignes complètes pour entraîner le détecteur."}

    sample = complete
    sampled = False
    if complete.shape[0] > MAX_ISOLATION_ROWS:
        sample = complete.sample(MAX_ISOLATION_ROWS, random_state=42)
        sampled = True

    model = IsolationForest(contamination=0.02, random_state=42, n_estimators=150)
    labels = model.fit_predict(sample.to_numpy())
    scores = model.score_samples(sample.to_numpy())
    is_anomaly = labels == -1

    order = np.argsort(scores)[: MAX_OUTLIER_EXAMPLES]
    examples = []
    for position in order:
        row_index = sample.index[position]
        examples.append({
            "row": int(row_index) if isinstance(row_index, (int, np.integer)) else str(row_index),
            "score": _num(scores[position]),
            "values": {col: _num(sample.iloc[position][col]) for col in numeric_cols},
        })

    return {
        "available": True,
        "columns": numeric_cols,
        "rows_evaluated": int(sample.shape[0]),
        "sampled": sampled,
        "anomaly_count": int(is_anomaly.sum()),
        "anomaly_pct": round(int(is_anomaly.sum()) / sample.shape[0] * 100, 2),
        "contamination": 0.02,
        "examples": examples,
        "note": "Isolation Forest isole les lignes atypiques par la combinaison de leurs valeurs. "
                "Le taux attendu est fixé à 2 % : le modèle signale donc environ 2 % des lignes, "
                "les plus isolées — c'est un classement, pas un verdict.",
    }


# --------------------------------------------------------------------------
# Onglet « Suggestions »
# --------------------------------------------------------------------------

def cleaning_suggestions(df: pd.DataFrame, quality: dict, duplicates: dict, anomalies: dict) -> list[dict]:
    suggestions: list[dict] = []

    def add(priority: str, title: str, detail: str, action: str, columns: Optional[list[str]] = None):
        suggestions.append({
            "priority": priority, "title": title, "detail": detail,
            "action": action, "columns": columns or [],
        })

    if duplicates["duplicate_rows"] > 0:
        add("haute", "Supprimer les lignes dupliquées",
            f"{duplicates['duplicate_rows']} ligne(s) sont des copies exactes d'une ligne précédente "
            f"({duplicates['duplicate_rows_pct']} % du jeu).",
            "Dédoublonner en conservant la première occurrence.")

    for column in quality["per_column"]:
        name = column["column"]
        if column["missing"] > 0:
            pct_missing = column["missing"] / max(1, quality["n_rows"]) * 100
            if pct_missing > 60:
                add("haute", f"Écarter la colonne « {name} »",
                    f"{pct_missing:.1f} % de valeurs manquantes : toute imputation pèserait plus lourd "
                    "que l'information réellement présente.",
                    "Supprimer la colonne, ou la conserver uniquement comme indicateur de présence.", [name])
            elif pct_missing > 5:
                add("moyenne", f"Traiter les manquants de « {name} »",
                    f"{column['missing']} valeur(s) manquante(s) ({pct_missing:.1f} %).",
                    "Imputer selon la forme de la distribution, ou exclure ces lignes de l'analyse.", [name])
        if column["type_mismatches"] > 0:
            add("haute", f"Corriger les valeurs non conformes de « {name} »",
                f"{column['type_mismatches']} valeur(s) ne respectent pas le type « {column['type']} ».",
                "Corriger la saisie ou convertir explicitement ces valeurs.", [name])
        if column["sentinel_values"] > 0:
            add("moyenne", f"Convertir les marqueurs d'absence de « {name} »",
                f"{column['sentinel_values']} valeur(s) du type « N/A », « -999 » : elles passent les "
                "contrôles de type mais ne portent aucune information.",
                "Remplacer ces marqueurs par de véritables valeurs manquantes.", [name])
        if column["inconsistent_formatting"] > 0:
            add("moyenne", f"Uniformiser l'écriture de « {name} »",
                f"{column['inconsistent_formatting']} libellé(s) ne diffèrent des autres que par la casse, "
                "les accents ou les espaces.",
                "Normaliser les libellés vers leur forme majoritaire.", [name])

    for group in duplicates["fuzzy_groups"][:10]:
        variants = ", ".join(f"« {v['value']} » ({v['count']})" for v in group["variants"][:4])
        add("moyenne", f"Fusionner des variantes dans « {group['column']} »",
            f"Ces libellés désignent probablement la même chose : {variants}.",
            f"Harmoniser vers « {group['canonical']} ».", [group["column"]])

    for column in anomalies["per_column"]:
        outliers = column.get("outliers")
        if outliers and outliers["iqr_count"] > 0 and outliers["iqr_pct"] > 5:
            add("basse", f"Examiner les valeurs extrêmes de « {column['column']} »",
                f"{outliers['iqr_count']} valeur(s) hors de [{outliers['lower_fence']:.4g} ; "
                f"{outliers['upper_fence']:.4g}], soit {outliers['iqr_pct']} % de la colonne.",
                "Vérifier s'il s'agit d'erreurs de saisie ou de cas réellement extrêmes — "
                "une distribution asymétrique en produit naturellement.", [column["column"]])

    multivariate = anomalies["multivariate"]
    if multivariate.get("available") and multivariate["anomaly_count"] > 0:
        # Priorité « info » et non « basse » : le détecteur signale une part fixe
        # des lignes (les 2 % les plus isolées) que le jeu soit sain ou non.
        # En faire un défaut à corriger laisserait croire à un problème inexistant.
        add("info", "Classement des lignes les plus atypiques",
            f"Les {multivariate['anomaly_count']} lignes les plus isolées ont été identifiées par leur "
            "combinaison de valeurs. Ce classement est produit systématiquement : il ne signale pas "
            "en soi un défaut du jeu de données.",
            "À consulter dans l'onglet Anomalies avant une modélisation, pour vérifier que ces lignes "
            "sont légitimes.")

    if not any(s["priority"] in ("haute", "moyenne", "basse") for s in suggestions):
        add("info", "Aucun nettoyage nécessaire",
            "Aucun problème structurel détecté : complétude, unicité, types et cohérence sont satisfaisants.",
            "Le jeu de données peut être analysé tel quel.")

    order = {"haute": 0, "moyenne": 1, "basse": 2, "info": 3}
    suggestions.sort(key=lambda s: order[s["priority"]])
    return suggestions


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------

def detailed_profile(df: pd.DataFrame) -> dict[str, Any]:
    quality = quality_report(df)
    duplicates = duplicate_report(df)
    anomalies = anomaly_report(df)
    return {
        "profile": {str(col): column_profile(df[col]) for col in df.columns},
        "quality": quality,
        "duplicates": duplicates,
        "anomalies": anomalies,
        "missing": missing_analysis(df),
        "suggestions": cleaning_suggestions(df, quality, duplicates, anomalies),
    }
