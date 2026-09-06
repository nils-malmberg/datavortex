"""Application des filtres avancés (Phase 8) et indicateurs associés.

L'intérêt d'un filtre n'est pas seulement de réduire les lignes : c'est de
comprendre *ce qu'il retire*. Ce module renvoie donc, en plus du résultat, la
contribution de chaque condition et un aperçu des lignes retenues ou écartées.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.filtering import evaluate_condition, evaluate_filter
from app.serialize import dataframe_to_records

MAX_PREVIEW_ROWS = 200


def _walk_conditions(node, path: str = "1") -> list[tuple[str, Any]]:
    """Aplatit l'arbre de filtre en une liste de (chemin, condition feuille)."""
    if node is None:
        return []
    if node.type == "condition":
        return [(path, node)]
    found: list[tuple[str, Any]] = []
    for i, child in enumerate(node.conditions, start=1):
        found.extend(_walk_conditions(child, f"{path}.{i}" if path else str(i)))
    return found


def _describe(condition) -> str:
    value = condition.value
    if isinstance(value, list):
        value = " / ".join(str(v) for v in value)
    return f"{condition.column} {condition.operator}" + (f" {value}" if value is not None else "")


def apply_advanced_filter(
    session,
    filter_node,
    invert: bool = False,
    preview_rows: int = 50,
    preview_mode: str = "all",
) -> dict[str, Any]:
    """Applique un filtre et renvoie le résultat accompagné de ses indicateurs.

    `preview_mode` :
      - "all"     : aperçu du jeu complet, chaque ligne marquée retenue/écartée
                    (utile pour voir ce que le filtre écarte avant de valider) ;
      - "kept"    : uniquement les lignes conservées ;
      - "removed" : uniquement les lignes écartées.
    """
    df = session.df
    total = int(df.shape[0])

    if filter_node is None:
        mask = pd.Series(True, index=df.index)
    else:
        mask = evaluate_filter(df, filter_node).fillna(False).astype(bool)
    if invert:
        mask = ~mask

    session.active_filter = filter_node
    session.filtered_df = None if filter_node is None and not invert else df[mask]
    session.touch()

    kept = int(mask.sum())
    leaves = _walk_conditions(filter_node)

    # Contribution isolée de chaque condition : combien de lignes elle retient
    # à elle seule, indépendamment des autres.
    per_condition = []
    for path, condition in leaves:
        try:
            single = evaluate_condition(df, condition).fillna(False)
            matched = int(single.sum())
        except Exception:
            matched = None
        per_condition.append({
            "path": path,
            "id": condition.id,
            "column": condition.column,
            "operator": condition.operator,
            "label": _describe(condition),
            "matched_rows": matched,
            "matched_pct": round(matched / total * 100, 2) if (matched is not None and total) else None,
        })

    columns_affected = sorted({condition.column for _, condition in leaves})

    limit = max(1, min(MAX_PREVIEW_ROWS, preview_rows))
    if preview_mode == "kept":
        preview_df, preview_mask = df[mask].head(limit), None
    elif preview_mode == "removed":
        preview_df, preview_mask = df[~mask].head(limit), None
    else:
        preview_df = df.head(limit)
        preview_mask = mask.head(limit).tolist()

    return {
        "session_id": session.session_id,
        "filtered": session.filtered_df is not None,
        "inverted": invert,
        "columns": [str(c) for c in df.columns],
        "columns_affected": columns_affected,
        "n_columns_affected": len(columns_affected),
        "total_rows": kept,
        "total_rows_unfiltered": total,
        "removed_rows": total - kept,
        "kept_pct": round(kept / total * 100, 2) if total else 0.0,
        "removed_pct": round((total - kept) / total * 100, 2) if total else 0.0,
        "per_condition": per_condition,
        "preview_mode": preview_mode,
        "rows": dataframe_to_records(preview_df),
        "row_matches": preview_mask,
        "shown_rows": int(preview_df.shape[0]),
    }
