"""Évaluation des filtres (Phase 3) : conditions simples et groupes AND/OR imbriqués."""
from __future__ import annotations

import re

import pandas as pd

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type

VALUE_REQUIRED_OPS = {
    "eq", "ne", "gt", "lt", "gte", "lte", "between", "in", "not_in",
    "contains", "starts_with", "ends_with", "regex", "year", "month", "day",
}
NO_VALUE_OPS = {"is_null", "is_not_null", "is_true", "is_false"}
ALL_OPERATORS = VALUE_REQUIRED_OPS | NO_VALUE_OPS


def _require_list(value, op: str, length: int | None = None):
    if not isinstance(value, (list, tuple)):
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' nécessite une liste de valeurs.")
    if length is not None and len(value) != length:
        raise AppError(400, "INVALID_FILTER_VALUE", f"L'opérateur '{op}' nécessite exactement {length} valeurs.")
    return value


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
