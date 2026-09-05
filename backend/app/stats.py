"""Calcul des statistiques descriptives par colonne."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.parsing import detect_column_type


def _clean_number(value: Any) -> Any:
    """Convertit les NaN/inf en None pour un JSON valide."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def numeric_stats(series: pd.Series) -> dict[str, Any]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "variance": None,
            "min": None,
            "q1": None,
            "q3": None,
            "max": None,
            "sum": None,
            "range": None,
        }
    return {
        "count": int(clean.count()),
        "mean": _clean_number(clean.mean()),
        "median": _clean_number(clean.median()),
        "std": _clean_number(clean.std()) if clean.count() > 1 else 0.0,
        "variance": _clean_number(clean.var()) if clean.count() > 1 else 0.0,
        "min": _clean_number(clean.min()),
        "q1": _clean_number(clean.quantile(0.25)),
        "q3": _clean_number(clean.quantile(0.75)),
        "max": _clean_number(clean.max()),
        "sum": _clean_number(clean.sum()),
        "range": _clean_number(clean.max() - clean.min()),
    }


def string_stats(series: pd.Series) -> dict[str, Any]:
    clean = series.dropna().astype(str)
    count = int(clean.count())
    unique = int(clean.nunique())
    if count == 0:
        mode = None
        top_values = []
    else:
        value_counts = clean.value_counts()
        mode = value_counts.index[0] if len(value_counts) else None
        top_values = [
            {"value": val, "count": int(cnt)}
            for val, cnt in value_counts.head(10).items()
        ]
    return {
        "count": count,
        "unique": unique,
        "mode": mode,
        "top_values": top_values,
    }


def column_summary(series: pd.Series) -> dict[str, Any]:
    """Résumé complet d'une colonne : type + stats adaptées + anomalies de base."""
    col_type = detect_column_type(series)
    n_total = int(len(series))
    n_missing = int(series.isna().sum())
    missing_pct = round((n_missing / n_total) * 100, 2) if n_total else 0.0

    if col_type in ("integer", "float"):
        stats = numeric_stats(series)
    elif col_type == "boolean":
        true_count = int(series.fillna(False).astype(bool).sum())
        false_count = int(n_total - n_missing - true_count)
        pct_true = round((true_count / (n_total - n_missing)) * 100, 2) if (n_total - n_missing) else 0.0
        stats = {"true_count": true_count, "false_count": false_count, "pct_true": pct_true}
    else:
        stats = string_stats(series)

    duplicated = int(series.duplicated().sum())

    return {
        "type": col_type,
        "missing_count": n_missing,
        "missing_pct": missing_pct,
        "duplicated_count": duplicated,
        "stats": stats,
    }


def dataframe_summary(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "n_rows": int(df.shape[0]),
        "n_columns": int(df.shape[1]),
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
        "columns": {col: column_summary(df[col]) for col in df.columns},
    }
