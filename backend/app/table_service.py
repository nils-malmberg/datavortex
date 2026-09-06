"""Service de lecture tabulaire paginée (Phase 8).

Le tableau de l'interface ne charge jamais tout le jeu de données : tri,
recherche, regroupement et pagination sont faits ici, sur le DataFrame complet,
et seule la tranche visible traverse le réseau. C'est ce qui rend l'affichage
utilisable sur des fichiers de plusieurs centaines de milliers de lignes.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type
from app.serialize import dataframe_to_records

MAX_PAGE_SIZE = 1000
MAX_GROUPS_LISTED = 200
NUMERIC_TYPES = ("integer", "float")


def _outlier_bounds(df: pd.DataFrame) -> dict[str, list[float]]:
    """Bornes de Tukey par colonne numérique, pour la mise en forme conditionnelle."""
    bounds: dict[str, list[float]] = {}
    for col in df.columns:
        if detect_column_type(df[col]) not in NUMERIC_TYPES:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce").dropna()
        if numeric.size < 4:
            continue
        q1, q3 = float(numeric.quantile(0.25)), float(numeric.quantile(0.75))
        iqr = q3 - q1
        if iqr <= 0:
            continue
        bounds[str(col)] = [q1 - 1.5 * iqr, q3 + 1.5 * iqr]
    return bounds


def _search_mask(df: pd.DataFrame, search: str, column: Optional[str]) -> pd.Series:
    needle = search.strip()
    if not needle:
        return pd.Series(True, index=df.index)
    if column:
        if column not in df.columns:
            raise column_not_found(column)
        targets = [column]
    else:
        targets = list(df.columns)
    mask = pd.Series(False, index=df.index)
    for col in targets:
        mask |= df[col].astype(str).str.contains(needle, case=False, na=False, regex=False)
    return mask


def read_rows(
    session,
    offset: int = 0,
    limit: int = 100,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    search: str = "",
    search_column: Optional[str] = None,
    group_by: Optional[str] = None,
) -> dict[str, Any]:
    df = session.active_df()
    total_rows = int(df.shape[0])

    if limit < 1 or limit > MAX_PAGE_SIZE:
        raise AppError(400, "INVALID_PAGE_SIZE", f"La taille de page doit être comprise entre 1 et {MAX_PAGE_SIZE}.")

    view = df
    if search:
        view = view[_search_mask(view, search, search_column)]
    matched_rows = int(view.shape[0])

    # Le regroupement se traduit par un tri sur la colonne : les lignes d'un même
    # groupe deviennent contiguës, ce que l'interface peut alors segmenter.
    sort_columns: list[str] = []
    ascending: list[bool] = []
    if group_by:
        if group_by not in df.columns:
            raise column_not_found(group_by)
        sort_columns.append(group_by)
        ascending.append(True)
    if sort_by:
        if sort_by not in df.columns:
            raise column_not_found(sort_by)
        if sort_by != group_by:
            sort_columns.append(sort_by)
            ascending.append(sort_dir != "desc")
    if sort_columns:
        view = view.sort_values(by=sort_columns, ascending=ascending, kind="mergesort")

    offset = max(0, min(offset, max(0, matched_rows - 1)))
    page = view.iloc[offset:offset + limit]

    groups = None
    if group_by:
        counts = view[group_by].astype(str).value_counts(dropna=False)
        groups = [
            {"value": str(value), "count": int(count)}
            for value, count in counts.head(MAX_GROUPS_LISTED).items()
        ]

    return {
        "session_id": session.session_id,
        "columns": [str(c) for c in df.columns],
        "column_types": {str(c): detect_column_type(df[c]) for c in df.columns},
        "rows": dataframe_to_records(page),
        # Indice d'origine de chaque ligne : c'est ce que vise « aller à la ligne N ».
        "row_indices": [int(i) if isinstance(i, (int, np.integer)) else str(i) for i in page.index],
        "total_rows": total_rows,
        "matched_rows": matched_rows,
        "offset": offset,
        "limit": limit,
        "shown_rows": int(page.shape[0]),
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "search": search,
        "search_column": search_column,
        "group_by": group_by,
        "groups": groups,
        "outlier_bounds": _outlier_bounds(df),
        "filtered": session.filtered_df is not None,
        "total_rows_unfiltered": int(session.df.shape[0]),
        "memory_usage_bytes": int(df.memory_usage(deep=True).sum()),
    }
