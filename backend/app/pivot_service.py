"""Tableaux croisés dynamiques (Phase 8).

Un pivot répond à « X en fonction de Y et Z » sous forme de tableau. Le mode
pourcentage est décliné en trois lectures (part du total, de la ligne, de la
colonne) car c'est la question posée qui change, pas le calcul.
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type
from app.serialize import dataframe_to_records

MAX_PIVOT_CELLS = 20_000
MAX_PIVOT_COLUMNS = 200
# Au-delà, une heatmap n'est plus lisible : le tableau reste complet, la figure
# ne montre que les premières lignes et le dit dans son titre.
MAX_HEATMAP_ROWS = 60
NUMERIC_TYPES = ("integer", "float")
NUMERIC_ONLY_AGGFUNCS = {"mean", "sum", "std", "var", "median"}

MARGIN_LABEL = "Total"
# Les modalités manquantes forment un groupe légitime : on les nomme lisiblement
# plutôt que de laisser apparaître le « nan » technique de pandas.
EMPTY_LABEL = "(vide)"

AGGFUNC_LABELS = {
    "mean": "moyenne", "sum": "somme", "count": "effectif", "min": "min",
    "max": "max", "std": "écart-type", "var": "variance", "median": "médiane",
    "nunique": "valeurs distinctes",
}


def _label(part: Any) -> str:
    text = str(part)
    return EMPTY_LABEL if text in ("nan", "NaT", "None", "") else text


def _flatten_columns(pivot: pd.DataFrame, column_fields: list[str]) -> pd.DataFrame:
    """Aplatit un MultiIndex de colonnes en libellés lisibles."""
    if not isinstance(pivot.columns, pd.MultiIndex):
        pivot.columns = [_label(c) for c in pivot.columns]
        return pivot
    pivot.columns = [" · ".join(_label(part) for part in col if str(part) != "") for col in pivot.columns]
    return pivot


def _apply_percentage(
    pivot: pd.DataFrame, mode: str, value_columns: list[str],
    index: list[str], has_margins: bool,
) -> pd.DataFrame:
    """Convertit les valeurs en pourcentages selon la lecture demandée.

    Les marges sont des totaux : les inclure dans un dénominateur le doublerait.
    Elles sont donc exclues des sommes de référence — en ligne comme en colonne —
    mais restent converties, pour lire « ce total pèse X % ».
    """
    if mode == "none":
        return pivot

    numeric = pivot[value_columns].astype(float)
    data_columns = [
        c for c in value_columns
        if c != MARGIN_LABEL and not c.endswith(f" · {MARGIN_LABEL}")
    ]
    if has_margins:
        is_margin_row = pivot[index].astype(str).eq(MARGIN_LABEL).any(axis=1)
    else:
        is_margin_row = pd.Series(False, index=pivot.index)
    data_rows = ~is_margin_row

    if mode == "total":
        denominator = float(numeric.loc[data_rows, data_columns].to_numpy().sum())
        if denominator == 0:
            raise AppError(422, "EMPTY_PIVOT", "Le total du tableau est nul : le pourcentage n'a pas de sens.")
        result = numeric / denominator * 100
    elif mode == "row":
        row_totals = numeric[data_columns].sum(axis=1).replace(0, np.nan)
        result = numeric.div(row_totals, axis=0) * 100
    else:  # column
        column_totals = numeric.loc[data_rows].sum(axis=0).replace(0, np.nan)
        result = numeric.div(column_totals, axis=1) * 100

    out = pivot.copy()
    out[value_columns] = result
    return out


def run_pivot(
    df: pd.DataFrame,
    index: list[str],
    columns: list[str],
    values: str,
    aggfunc: str = "mean",
    margins: bool = False,
    percentage: str = "none",
) -> dict[str, Any]:
    if not index:
        raise AppError(400, "MISSING_INDEX", "Sélectionnez au moins une colonne pour les lignes du tableau.")
    if not values:
        raise AppError(400, "MISSING_VALUES", "Sélectionnez la colonne de valeurs à agréger.")

    for col in [*index, *columns, values]:
        if col not in df.columns:
            raise column_not_found(col)

    overlap = set(index) & set(columns)
    if overlap:
        raise AppError(
            400, "OVERLAPPING_FIELDS",
            f"La colonne '{sorted(overlap)[0]}' ne peut pas servir à la fois de ligne et de colonne.",
        )

    if aggfunc in NUMERIC_ONLY_AGGFUNCS and detect_column_type(df[values]) not in NUMERIC_TYPES:
        raise AppError(
            400, "INVALID_COLUMN_TYPE",
            f"L'agrégation « {AGGFUNC_LABELS.get(aggfunc, aggfunc)} » demande une colonne de valeurs numérique, "
            f"or '{values}' ne l'est pas. Utilisez effectif ou valeurs distinctes.",
        )

    n_rows = int(df.groupby(index, dropna=False, observed=True).ngroups)
    n_cols = int(df.groupby(columns, dropna=False, observed=True).ngroups) if columns else 1
    if n_cols > MAX_PIVOT_COLUMNS:
        raise AppError(
            422, "TOO_MANY_PIVOT_COLUMNS",
            f"Le tableau produirait {n_cols} colonnes (maximum {MAX_PIVOT_COLUMNS}). "
            "Choisissez une colonne moins fine pour l'axe horizontal.",
        )
    if n_rows * n_cols > MAX_PIVOT_CELLS:
        raise AppError(
            422, "PIVOT_TOO_LARGE",
            f"Le tableau produirait {n_rows * n_cols} cellules (maximum {MAX_PIVOT_CELLS}). "
            "Réduisez le nombre de modalités croisées.",
        )

    try:
        pivot = pd.pivot_table(
            df, index=index, columns=columns or None, values=values,
            aggfunc=aggfunc, margins=margins, margins_name=MARGIN_LABEL,
            observed=True, dropna=False,
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise AppError(400, "PIVOT_FAILED", f"Impossible de construire ce tableau croisé : {exc}")

    if isinstance(pivot, pd.Series):
        pivot = pivot.to_frame(name=values)

    pivot = _flatten_columns(pivot, columns)
    value_columns = [str(c) for c in pivot.columns]
    pivot = pivot.reset_index()
    # Les libellés de lignes doivent rester du texte, y compris la marge.
    for col in index:
        pivot[col] = pivot[col].map(_label)

    pivot = _apply_percentage(pivot, percentage, value_columns, index, margins)

    figure = _heatmap_figure(pivot, index, value_columns, values, aggfunc, percentage)

    return {
        "columns": [str(c) for c in pivot.columns],
        "index_columns": list(index),
        "value_columns": value_columns,
        "rows": dataframe_to_records(pivot),
        "n_rows": int(pivot.shape[0]),
        "heatmap_truncated": bool(pivot.shape[0] > MAX_HEATMAP_ROWS),
        "n_value_columns": len(value_columns),
        "margins": margins,
        "percentage": percentage,
        "aggfunc": aggfunc,
        "values": values,
        "table": pivot,
        "figure": figure,
    }


def _heatmap_figure(
    pivot: pd.DataFrame, index: list[str], value_columns: list[str],
    values: str, aggfunc: str, percentage: str,
) -> Optional[go.Figure]:
    if pivot.empty or not value_columns:
        return None
    display = pivot.head(MAX_HEATMAP_ROWS)
    matrix = display[value_columns].apply(pd.to_numeric, errors="coerce")
    if matrix.isna().all().all():
        return None

    labels = display[index].astype(str).agg(" · ".join, axis=1) if len(index) > 1 else display[index[0]].astype(str)
    suffix = " (%)" if percentage != "none" else ""
    truncated = f" — {MAX_HEATMAP_ROWS} premières lignes sur {pivot.shape[0]}" if pivot.shape[0] > MAX_HEATMAP_ROWS else ""
    text_format = ".1f" if percentage != "none" else ".4g"

    # Le texte est pré-formaté : sinon les cellules vides afficheraient « 0.00 ».
    annotations = [
        ["" if pd.isna(v) else format(v, text_format) for v in row]
        for row in matrix.to_numpy()
    ]

    fig = go.Figure(go.Heatmap(
        z=matrix.to_numpy(),
        x=value_columns,
        y=labels.tolist(),
        colorscale="Viridis",
        text=annotations,
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False,
        hovertemplate="%{y} · %{x}<br>%{z:.6g}<extra></extra>",
        colorbar=dict(title=f"{AGGFUNC_LABELS.get(aggfunc, aggfunc)}{suffix}", thickness=14),
    ))
    fig.update_layout(
        title=f"{AGGFUNC_LABELS.get(aggfunc, aggfunc)} de {values}{suffix}{truncated}",
        margin=dict(t=60, r=20, b=110, l=140),
        xaxis=dict(tickangle=-40, automargin=True),
        yaxis=dict(automargin=True, autorange="reversed"),
    )
    return fig
