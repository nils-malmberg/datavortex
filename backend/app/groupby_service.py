"""Agrégations par groupe (Phase 8).

Traduit une demande de l'interface — « moyenne de X et somme de Y, par Z » — en
un `groupby().agg()` pandas, avec des messages d'erreur qui expliquent pourquoi
une combinaison est refusée plutôt que de renvoyer un tableau vide.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from app.errors import AppError, column_not_found
from app.parsing import detect_column_type
from app.plotting_service import DEFAULT_QUALITATIVE
from app.serialize import dataframe_to_records

MAX_GROUPS = 5000
MAX_BAR_CATEGORIES = 30
NUMERIC_TYPES = ("integer", "float")

# Agrégations qui exigent une colonne numérique : appliquées à du texte, elles
# lèveraient une erreur pandas peu lisible.
NUMERIC_ONLY_FUNCS = {"mean", "sum", "std", "var", "sem", "median", "quantile"}

FUNC_LABELS = {
    "mean": "moyenne", "sum": "somme", "count": "effectif", "min": "min", "max": "max",
    "std": "écart-type", "var": "variance", "sem": "erreur standard", "median": "médiane",
    "quantile": "quantile", "first": "première", "last": "dernière", "nunique": "valeurs distinctes",
}


def _resolve_alias(spec) -> str:
    if spec.alias:
        return spec.alias
    if spec.func == "quantile":
        return f"{spec.column}_q{spec.quantile:g}"
    return f"{spec.column}_{spec.func}"


def _aggregate(series: pd.Series, spec):
    if spec.func == "quantile":
        if not 0 <= spec.quantile <= 1:
            raise AppError(400, "INVALID_QUANTILE", "Le quantile doit être compris entre 0 et 1.")
        return series.quantile(spec.quantile)
    if spec.func == "sem":
        return series.sem()
    return getattr(series, spec.func)()


def run_groupby(
    df: pd.DataFrame,
    group_by: list[str],
    aggregations: list,
    sort_by: Optional[str] = None,
    sort_ascending: bool = True,
    limit: int = 500,
) -> dict[str, Any]:
    if not group_by:
        raise AppError(400, "MISSING_GROUP_BY", "Sélectionnez au moins une colonne de regroupement.")
    if not aggregations:
        raise AppError(400, "MISSING_AGGREGATIONS", "Sélectionnez au moins une agrégation à calculer.")

    for col in group_by:
        if col not in df.columns:
            raise column_not_found(col)

    aliases: list[str] = []
    for spec in aggregations:
        if spec.column not in df.columns:
            raise column_not_found(spec.column)
        if spec.func in NUMERIC_ONLY_FUNCS and detect_column_type(df[spec.column]) not in NUMERIC_TYPES:
            raise AppError(
                400, "INVALID_COLUMN_TYPE",
                f"L'agrégation « {FUNC_LABELS.get(spec.func, spec.func)} » demande une colonne numérique, "
                f"or '{spec.column}' ne l'est pas. Utilisez effectif, min, max ou valeurs distinctes.",
            )
        alias = _resolve_alias(spec)
        if alias in aliases or alias in group_by:
            raise AppError(
                400, "DUPLICATE_ALIAS",
                f"Le nom de résultat '{alias}' est utilisé deux fois. Renommez l'une des agrégations.",
            )
        aliases.append(alias)

    n_groups = int(df.groupby(group_by, dropna=False, observed=True).ngroups)
    if n_groups > MAX_GROUPS:
        raise AppError(
            422, "TOO_MANY_GROUPS",
            f"Le regroupement produit {n_groups} groupes (maximum {MAX_GROUPS}). "
            "Choisissez moins de colonnes de regroupement, ou une colonne moins fine.",
        )

    grouped = df.groupby(group_by, dropna=False, observed=True)
    columns: dict[str, pd.Series] = {}
    for spec, alias in zip(aggregations, aliases):
        columns[alias] = _aggregate(grouped[spec.column], spec)

    result = pd.DataFrame(columns).reset_index()

    if sort_by:
        if sort_by not in result.columns:
            raise AppError(
                400, "INVALID_SORT_COLUMN",
                f"Impossible de trier sur '{sort_by}' : ce n'est ni une colonne de regroupement "
                f"ni un résultat d'agrégation. Colonnes disponibles : {', '.join(result.columns)}.",
            )
        result = result.sort_values(by=sort_by, ascending=sort_ascending, kind="mergesort")

    limited = result.head(max(1, min(MAX_GROUPS, limit)))

    return {
        "columns": [str(c) for c in result.columns],
        "group_columns": list(group_by),
        "value_columns": aliases,
        "rows": dataframe_to_records(limited),
        "group_count": n_groups,
        "shown_rows": int(limited.shape[0]),
        "truncated": bool(result.shape[0] > limited.shape[0]),
        "table": result,
        "figure": _bar_figure(limited, group_by, aliases),
    }


def _bar_figure(result: pd.DataFrame, group_by: list[str], aliases: list[str]) -> Optional[go.Figure]:
    """Diagramme en barres des résultats — une série par agrégation."""
    if result.empty or not aliases:
        return None
    display = result.head(MAX_BAR_CATEGORIES)
    labels = display[group_by].astype(str).agg(" · ".join, axis=1) if len(group_by) > 1 else display[group_by[0]].astype(str)

    fig = go.Figure()
    numeric_aliases = [a for a in aliases if pd.api.types.is_numeric_dtype(display[a])]
    if not numeric_aliases:
        return None
    for i, alias in enumerate(numeric_aliases):
        fig.add_trace(go.Bar(
            x=labels, y=display[alias], name=alias,
            marker_color=DEFAULT_QUALITATIVE[i % len(DEFAULT_QUALITATIVE)],
            hovertemplate=f"%{{x}}<br>{alias} = %{{y:.6g}}<extra></extra>",
        ))
    truncated = " (30 premiers groupes)" if result.shape[0] > MAX_BAR_CATEGORIES else ""
    fig.update_layout(
        barmode="group",
        title=f"Agrégations par {' × '.join(group_by)}{truncated}",
        xaxis_title=" × ".join(group_by),
        yaxis_title="Valeur agrégée",
        margin=dict(t=60, r=20, b=100, l=70),
        xaxis=dict(tickangle=-40, automargin=True),
    )
    return fig
