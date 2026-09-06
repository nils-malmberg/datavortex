"""Évaluation des filtres (Phase 3) : conditions simples et groupes AND/OR imbriqués."""
from __future__ import annotations

import re

import pandas as pd

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type

VALUE_REQUIRED_OPS = {
    "eq", "ne", "gt", "lt", "gte", "lte", "between", "in", "not_in",
    "contains", "starts_with", "ends_with", "regex", "year", "month", "day",
    "top_n", "bottom_n", "outlier_zscore", "not_outlier_zscore",
}
NO_VALUE_OPS = {
    "is_null", "is_not_null", "is_true", "is_false",
    "outlier_iqr", "not_outlier_iqr",
}
# Opérateurs qui raisonnent sur la colonne entière (rang, dispersion) et non
# valeur par valeur : ils exigent une colonne numérique.
COLUMN_WIDE_OPS = {
    "top_n", "bottom_n", "outlier_iqr", "not_outlier_iqr",
    "outlier_zscore", "not_outlier_zscore",
}
ALL_OPERATORS = VALUE_REQUIRED_OPS | NO_VALUE_OPS


def _require_list(value, op: str, length: int | None = None):
    if not isinstance(value, (list, tuple)):
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' nécessite une liste de valeurs.")
    if length is not None and len(value) != length:
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' nécessite exactement {length} valeurs.")
    return value


def _numeric_column(col: pd.Series, op: str) -> pd.Series:
    numeric = pd.to_numeric(col, errors="coerce")
    if numeric.notna().sum() == 0:
        raise AppError(
            400, "INVALID_COLUMN_TYPE",
            f"L'opérateur '{op}' nécessite une colonne numérique.",
        )
    return numeric


def _positive_int(value, op: str) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' attend un nombre entier de lignes.")
    if count < 1:
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' attend un nombre de lignes strictement positif.")
    return count


def _iqr_outlier_mask(numeric: pd.Series) -> pd.Series:
    """Règle de Tukey : hors de [Q1 - 1,5·IQR ; Q3 + 1,5·IQR]."""
    q1, q3 = numeric.quantile(0.25), numeric.quantile(0.75)
    iqr = q3 - q1
    return (numeric < q1 - 1.5 * iqr) | (numeric > q3 + 1.5 * iqr)


def _zscore_outlier_mask(numeric: pd.Series, threshold: float) -> pd.Series:
    std = numeric.std()
    if not std or pd.isna(std) or std == 0:
        # Colonne constante : aucun point n'est atypique.
        return pd.Series(False, index=numeric.index)
    return ((numeric - numeric.mean()).abs() / std) > threshold


def evaluate_condition(df: pd.DataFrame, cond) -> pd.Series:
    if cond.column not in df.columns:
        raise column_not_found(cond.column)
    op = cond.operator
    if op not in ALL_OPERATORS:
        raise AppError(400, "UNKNOWN_OPERATOR", f"Opérateur de filtre inconnu : '{op}'")
    if op in VALUE_REQUIRED_OPS and cond.value is None:
        raise AppError(400, "MISSING_FILTER_VALUE", f"L'opérateur '{op}' nécessite une valeur.")

    col = df[cond.column]
    val = cond.value
    col_type = detect_column_type(col)

    if op in COLUMN_WIDE_OPS:
        numeric = _numeric_column(col, op)
        if op == "top_n":
            # rank 'first' départage les ex æquo : on garde exactement N lignes.
            return numeric.rank(method="first", ascending=False) <= _positive_int(val, op)
        if op == "bottom_n":
            return numeric.rank(method="first", ascending=True) <= _positive_int(val, op)
        if op == "outlier_iqr":
            return _iqr_outlier_mask(numeric).fillna(False)
        if op == "not_outlier_iqr":
            return (~_iqr_outlier_mask(numeric)).fillna(False) & numeric.notna()
        threshold = float(val) if val is not None else 3.0
        mask = _zscore_outlier_mask(numeric, threshold)
        return mask.fillna(False) if op == "outlier_zscore" else (~mask).fillna(False) & numeric.notna()

    if op == "is_null":
        return col.isna()
    if op == "is_not_null":
        return col.notna()
    if op == "is_true":
        return col.fillna(False).astype(bool)
    if op == "is_false":
        return ~col.fillna(False).astype(bool)

    if col_type == "datetime" and op in ("eq", "ne", "gt", "lt", "gte", "lte", "between", "year", "month", "day"):
        col = pd.to_datetime(col, errors="coerce")
        if op in ("year", "month", "day"):
            return getattr(col.dt, op) == val
        if op == "between":
            lo, hi = _require_list(val, op, length=2)
            return col.between(pd.to_datetime(lo), pd.to_datetime(hi))
        val = pd.to_datetime(val)

    if op in ("eq", "equals"):
        return col == val
    if op == "ne":
        return col != val
    if op == "gt":
        return col > val
    if op == "lt":
        return col < val
    if op == "gte":
        return col >= val
    if op == "lte":
        return col <= val
    if op == "between":
        lo, hi = _require_list(val, op, length=2)
        return col.between(lo, hi)
    if op == "in":
        return col.isin(_require_list(val, op))
    if op == "not_in":
        return ~col.isin(_require_list(val, op))
    if op == "contains":
        return col.astype(str).str.contains(str(val), case=False, na=False, regex=False)
    if op == "starts_with":
        return col.astype(str).str.startswith(str(val)).fillna(False)
    if op == "ends_with":
        return col.astype(str).str.endswith(str(val)).fillna(False)
    if op == "regex":
        try:
            return col.astype(str).str.contains(str(val), regex=True, na=False)
        except re.error as exc:
            raise AppError(400, "INVALID_REGEX", f"Expression régulière invalide : {exc}")

    raise AppError(400, "UNKNOWN_OPERATOR", f"Opérateur non implémenté : '{op}'")  # pragma: no cover


def evaluate_filter(df: pd.DataFrame, node) -> pd.Series:
    if node is None:
        return pd.Series(True, index=df.index)
    if node.type == "condition":
        return evaluate_condition(df, node)
    if node.type == "group":
        if not node.conditions:
            return pd.Series(True, index=df.index)
        masks = [evaluate_filter(df, c) for c in node.conditions]
        combined = masks[0]
        for mask in masks[1:]:
            combined = (combined & mask) if node.logic == "AND" else (combined | mask)
        return combined
    raise AppError(400, "INVALID_FILTER_NODE", "Nœud de filtre invalide.")  # pragma: no cover
