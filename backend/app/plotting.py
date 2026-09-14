"""Construction des figures Plotly pour les visualisations 1D/2D/3D (Phase 2)."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats

from app.errors import AppError, column_not_found
from app.models import MultiSeriesPlotRequest, Plot1DRequest, Plot2DRequest, Plot3DRequest
from app.parsing import detect_column_type

MAX_CATEGORIES = 20
MAX_BINS = 200
MIN_BINS = 2
MARKER_SIZE_RANGE = (6, 30)
MAX_SURFACE_CELLS = 2500

PALETTE = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
    "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC",
]

# Nombre maximal de points envoyés au navigateur pour une trace point à point.
# Une figure Plotly transporte ses données brutes : un nuage de points sur
# 3,2 millions de lignes pesait 36 Mo de JSON et bloquait l'onglet pendant sa
# désérialisation, pour un résultat visuel identique — au-delà de quelques
# dizaines de milliers de points superposés, l'œil ne distingue plus qu'une
# tache uniforme. Réglable via DATAVORTEX_MAX_PLOT_POINTS.
MAX_PLOT_POINTS = int(os.environ.get("DATAVORTEX_MAX_PLOT_POINTS", "50000"))

# Types dont la trace transporte une valeur par ligne : ce sont les seuls
# concernés. Un histogramme groupé ou une heatmap agrègent côté serveur et
# n'envoient déjà que le résultat.
POINT_BASED_TYPES = {
    "scatter", "line", "area", "bubble", "scatter3d", "box", "violin", "histogram", "kde",
    "joint", "strip", "violin_swarm", "ridge", "hexbin",
}


def plot_frame(df: pd.DataFrame, plot_type: str) -> tuple[pd.DataFrame, bool]:
    """Échantillonne les données d'une figure point à point si nécessaire.

    Renvoie le DataFrame à tracer et un booléen disant s'il a été réduit, pour
    que la figure puisse l'annoncer : un graphique tracé sur un échantillon ne
    doit jamais se présenter comme exhaustif.

    L'échantillon est aléatoire à graine fixe — un tirage régulier (une ligne
    sur N) donnerait un résultat trompeur sur des données déjà triées.
    """
    if plot_type not in POINT_BASED_TYPES or len(df) <= MAX_PLOT_POINTS:
        return df, False
    return df.sample(MAX_PLOT_POINTS, random_state=42).sort_index(), True


def note_sampling(fig: go.Figure, total_rows: int) -> None:
    """Mentionne l'échantillonnage sur la figure elle-même."""
    fig.add_annotation(
        text=f"Échantillon de {MAX_PLOT_POINTS:,} points sur {total_rows:,}".replace(",", " "),
        xref="paper", yref="paper", x=1, y=1.04, showarrow=False,
        font=dict(size=10, color="#64748b"), xanchor="right",
    )


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col and col not in df.columns:
            raise column_not_found(col)


def _is_numeric(df: pd.DataFrame, col: str) -> bool:
    return detect_column_type(df[col]) in ("integer", "float")


def _require_numeric(df: pd.DataFrame, col: str) -> None:
    if not _is_numeric(df, col):
        raise AppError(
            400,
            "INVALID_COLUMN_TYPE",
            f"La colonne '{col}' doit être numérique pour ce type de graphique.",
        )


def _numeric_series(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col], errors="coerce").dropna()


def _default_title(text: str, override: str | None) -> str:
    return override or text


def _normalize_sizes(series: pd.Series) -> np.ndarray:
    values = pd.to_numeric(series, errors="coerce").fillna(0).to_numpy(dtype=float)
    vmin, vmax = values.min(), values.max()
    lo, hi = MARKER_SIZE_RANGE
    if vmax - vmin == 0:
        return np.full_like(values, (lo + hi) / 2)
    scaled = (values - vmin) / (vmax - vmin)
    return lo + scaled * (hi - lo)


# --------------------------------------------------------------------------
# 1D
# --------------------------------------------------------------------------

def build_1d_figure(df: pd.DataFrame, req: Plot1DRequest) -> go.Figure:
    _require_columns(df, [req.column, req.group_by] if req.group_by else [req.column])
    total_rows = len(df)
    df, sampled = plot_frame(df, req.plot_type)
    bins = max(MIN_BINS, min(MAX_BINS, req.bins))
    fig = go.Figure()

    if req.plot_type == "histogram":
        _require_numeric(df, req.column)
        if req.group_by:
            for i, (group_val, sub) in enumerate(df.groupby(req.group_by, dropna=True)):
                values = _numeric_series(sub, req.column)
                fig.add_trace(go.Histogram(x=values, name=str(group_val), nbinsx=bins,
                                            marker_color=PALETTE[i % len(PALETTE)], opacity=0.65))
            fig.update_layout(barmode="overlay")
        else:
            values = _numeric_series(df, req.column)
            fig.add_trace(go.Histogram(x=values, nbinsx=bins, marker_color=PALETTE[0]))
        fig.update_layout(
            title=_default_title(f"Histogramme de {req.column}", req.title),
            xaxis_title=req.column,
            yaxis_title="Fréquence",
        )

    elif req.plot_type in ("box", "violin"):
        _require_numeric(df, req.column)
        trace_cls = go.Box if req.plot_type == "box" else go.Violin
        if req.group_by:
            for i, (group_val, sub) in enumerate(df.groupby(req.group_by, dropna=True)):
                values = _numeric_series(sub, req.column)
                kwargs = {"box_visible": True, "meanline_visible": True} if req.plot_type == "violin" else {}
                fig.add_trace(trace_cls(y=values, name=str(group_val),
                                         marker_color=PALETTE[i % len(PALETTE)], **kwargs))
        else:
            values = _numeric_series(df, req.column)
            kwargs = {"box_visible": True, "meanline_visible": True} if req.plot_type == "violin" else {}
            fig.add_trace(trace_cls(y=values, name=req.column, marker_color=PALETTE[0], **kwargs))
        label = "Box plot" if req.plot_type == "box" else "Violin plot"
        fig.update_layout(
            title=_default_title(f"{label} de {req.column}" + (f" par {req.group_by}" if req.group_by else ""), req.title),
            yaxis_title=req.column,
        )

    elif req.plot_type == "kde":
        _require_numeric(df, req.column)
        values = _numeric_series(df, req.column)
        if values.nunique() < 2:
            raise AppError(422, "INSUFFICIENT_DATA", "Pas assez de valeurs distinctes pour calculer une densité (KDE).")
        kde = scipy_stats.gaussian_kde(values)
        grid = np.linspace(values.min(), values.max(), 200)
        density = kde(grid)
        fig.add_trace(go.Scatter(x=grid, y=density, mode="lines", fill="tozeroy", line_color=PALETTE[0]))
        fig.update_layout(
            title=_default_title(f"Densité (KDE) de {req.column}", req.title),
            xaxis_title=req.column,
            yaxis_title="Densité",
        )

    elif req.plot_type in ("bar", "pie"):
        counts = df[req.column].dropna().astype(str).value_counts().head(MAX_CATEGORIES)
        if req.plot_type == "bar":
            fig.add_trace(go.Bar(x=counts.index.tolist(), y=counts.values.tolist(), marker_color=PALETTE[0]))
            fig.update_layout(
                title=_default_title(f"Répartition de {req.column}", req.title),
                xaxis_title=req.column,
                yaxis_title="Nombre",
            )
        else:
            fig.add_trace(go.Pie(labels=counts.index.tolist(), values=counts.values.tolist()))
            fig.update_layout(title=_default_title(f"Répartition de {req.column}", req.title))

    else:  # pragma: no cover - garanti par Literal côté Pydantic
        raise AppError(400, "UNKNOWN_PLOT_TYPE", f"Type de graphique 1D inconnu : {req.plot_type}")

    if sampled:
        note_sampling(fig, total_rows)
    return fig


# --------------------------------------------------------------------------
# 2D
# --------------------------------------------------------------------------

def _grouped_traces(df: pd.DataFrame, x: str, y: str, color_by: str | None, mode: str) -> list[go.Scatter]:
    traces = []
    if color_by:
        for i, (group_val, sub) in enumerate(df.groupby(color_by, dropna=True)):
            sub_sorted = sub.sort_values(by=x) if mode == "lines" else sub
            traces.append(go.Scatter(
                x=sub_sorted[x], y=sub_sorted[y], mode=mode, name=str(group_val),
                marker=dict(color=PALETTE[i % len(PALETTE)]),
                line=dict(color=PALETTE[i % len(PALETTE)]) if mode == "lines" else None,
            ))
    else:
        sub_sorted = df.sort_values(by=x) if mode == "lines" else df
        traces.append(go.Scatter(x=sub_sorted[x], y=sub_sorted[y], mode=mode, marker=dict(color=PALETTE[0])))
    return traces


def build_2d_figure(df: pd.DataFrame, req: Plot2DRequest) -> go.Figure:
    total_rows = len(df)
    df, sampled = plot_frame(df, req.plot_type)
    fig = go.Figure()

    if req.plot_type == "heatmap":
        columns = req.columns or [c for c in df.columns if _is_numeric(df, c)]
        _require_columns(df, columns)
        numeric_cols = [c for c in columns if _is_numeric(df, c)]
        if len(numeric_cols) < 2:
            raise AppError(422, "INSUFFICIENT_COLUMNS",
                            "Il faut au moins 2 colonnes numériques pour une heatmap de corrélation.")
        corr = df[numeric_cols].corr()
        fig.add_trace(go.Heatmap(
            z=corr.values, x=corr.columns.tolist(), y=corr.columns.tolist(),
            colorscale="RdBu", zmin=-1, zmax=1, zmid=0,
            text=np.round(corr.values, 2), texttemplate="%{text}",
        ))
        fig.update_layout(title=_default_title("Heatmap de corrélation", req.title))
        return fig

    if not req.x or not req.y:
        raise AppError(400, "MISSING_AXIS", "Les colonnes 'x' et 'y' sont requises pour ce type de graphique.")
    _require_columns(df, [req.x, req.y, req.color_by, req.size_by])

    if req.plot_type == "scatter":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        if req.size_by:
            _require_numeric(df, req.size_by)
            sizes = _normalize_sizes(df[req.size_by])
            fig.add_trace(go.Scatter(x=df[req.x], y=df[req.y], mode="markers",
                                      marker=dict(size=sizes, color=PALETTE[0], opacity=0.75)))
        elif req.color_by:
            if _is_numeric(df, req.color_by):
                fig.add_trace(go.Scatter(x=df[req.x], y=df[req.y], mode="markers", marker=dict(
                    color=df[req.color_by], colorscale="Viridis", showscale=True,
                    colorbar=dict(title=req.color_by),
                )))
            else:
                for i, (group_val, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
                    fig.add_trace(go.Scatter(x=sub[req.x], y=sub[req.y], mode="markers", name=str(group_val),
                                              marker=dict(color=PALETTE[i % len(PALETTE)])))
        else:
            fig.add_trace(go.Scatter(x=df[req.x], y=df[req.y], mode="markers", marker=dict(color=PALETTE[0])))
        fig.update_layout(
            title=_default_title(f"{req.y} vs {req.x}", req.title),
            xaxis_title=req.x, yaxis_title=req.y,
        )

    elif req.plot_type == "bubble":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        if not req.size_by:
            raise AppError(400, "MISSING_SIZE_BY", "Le champ 'size_by' est requis pour un bubble chart.")
        _require_numeric(df, req.size_by)
        sizes = _normalize_sizes(df[req.size_by])
        if req.color_by and not _is_numeric(df, req.color_by):
            for i, (group_val, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
                sub_sizes = _normalize_sizes(sub[req.size_by])
                fig.add_trace(go.Scatter(x=sub[req.x], y=sub[req.y], mode="markers", name=str(group_val),
                                          marker=dict(size=sub_sizes, color=PALETTE[i % len(PALETTE)], opacity=0.75)))
        else:
            marker = dict(size=sizes, opacity=0.75)
            if req.color_by:
                marker.update(color=df[req.color_by], colorscale="Viridis", showscale=True,
                               colorbar=dict(title=req.color_by))
            else:
                marker.update(color=PALETTE[0])
            fig.add_trace(go.Scatter(x=df[req.x], y=df[req.y], mode="markers", marker=marker))
        fig.update_layout(
            title=_default_title(f"{req.y} vs {req.x} (taille: {req.size_by})", req.title),
            xaxis_title=req.x, yaxis_title=req.y,
        )

    elif req.plot_type == "line":
        _require_numeric(df, req.y)
        for trace in _grouped_traces(df, req.x, req.y, req.color_by, mode="lines"):
            fig.add_trace(trace)
        fig.update_layout(
            title=_default_title(f"{req.y} en fonction de {req.x}", req.title),
            xaxis_title=req.x, yaxis_title=req.y,
        )

    elif req.plot_type == "hexbin":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        bins = max(MIN_BINS, min(MAX_BINS, req.bins))
        fig.add_trace(go.Histogram2d(x=df[req.x], y=df[req.y], nbinsx=bins, nbinsy=bins, colorscale="Viridis"))
        fig.update_layout(
            title=_default_title(f"Densité 2D : {req.y} vs {req.x}", req.title),
            xaxis_title=req.x, yaxis_title=req.y,
        )

    elif req.plot_type == "bar_grouped":
        group_col = req.color_by
        if not group_col:
            raise AppError(400, "MISSING_COLOR_BY", "Le champ 'color_by' (colonne de groupement) est requis.")
        if group_col == req.x:
            raise AppError(400, "SAME_COLUMN",
                            "Les colonnes 'x' et 'color_by' doivent être différentes pour un bar chart groupé.")
        if _is_numeric(df, req.y):
            agg = df.groupby([req.x, group_col])[req.y].mean().reset_index()
            y_label = f"Moyenne de {req.y}"
        else:
            agg = df.groupby([req.x, group_col]).size().reset_index(name=req.y)
            y_label = "Nombre"
        for i, (group_val, sub) in enumerate(agg.groupby(group_col)):
            fig.add_trace(go.Bar(x=sub[req.x], y=sub[req.y], name=str(group_val),
                                  marker_color=PALETTE[i % len(PALETTE)]))
        fig.update_layout(
            barmode="group",
            title=_default_title(f"{y_label} par {req.x} et {group_col}", req.title),
            xaxis_title=req.x, yaxis_title=y_label,
        )

    else:  # pragma: no cover
        raise AppError(400, "UNKNOWN_PLOT_TYPE", f"Type de graphique 2D inconnu : {req.plot_type}")

    if sampled:
        note_sampling(fig, total_rows)
    return fig


# --------------------------------------------------------------------------
# 3D
# --------------------------------------------------------------------------

def build_3d_figure(df: pd.DataFrame, req: Plot3DRequest) -> go.Figure:
    _require_columns(df, [req.x, req.y, req.z, req.color_by])
    total_rows = len(df)
    df, sampled = plot_frame(df, req.plot_type)
    fig = go.Figure()

    if req.plot_type == "scatter3d":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        _require_numeric(df, req.z)
        marker = dict(size=4)
        if req.color_by:
            if _is_numeric(df, req.color_by):
                marker.update(color=df[req.color_by], colorscale="Viridis", showscale=True,
                               colorbar=dict(title=req.color_by))
                fig.add_trace(go.Scatter3d(x=df[req.x], y=df[req.y], z=df[req.z], mode="markers", marker=marker))
            else:
                for i, (group_val, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
                    fig.add_trace(go.Scatter3d(x=sub[req.x], y=sub[req.y], z=sub[req.z], mode="markers",
                                                name=str(group_val),
                                                marker=dict(size=4, color=PALETTE[i % len(PALETTE)])))
        else:
            marker.update(color=PALETTE[0])
            fig.add_trace(go.Scatter3d(x=df[req.x], y=df[req.y], z=df[req.z], mode="markers", marker=marker))
        fig.update_layout(
            title=_default_title(f"Scatter 3D : {req.x}, {req.y}, {req.z}", req.title),
            scene=dict(xaxis_title=req.x, yaxis_title=req.y, zaxis_title=req.z),
        )

    elif req.plot_type == "surface":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        _require_numeric(df, req.z)
        pivot = df.pivot_table(index=req.y, columns=req.x, values=req.z, aggfunc="mean")
        if pivot.shape[0] * pivot.shape[1] > MAX_SURFACE_CELLS:
            raise AppError(
                422, "GRID_TOO_LARGE",
                "Trop de combinaisons uniques de x/y pour une surface. "
                "Choisissez des colonnes avec moins de valeurs distinctes, ou utilisez un scatter 3D.",
            )
        fig.add_trace(go.Surface(z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
                                  colorscale="Viridis"))
        fig.update_layout(
            title=_default_title(f"Surface : {req.z} = f({req.x}, {req.y})", req.title),
            scene=dict(xaxis_title=req.x, yaxis_title=req.y, zaxis_title=req.z),
        )

    else:  # pragma: no cover
        raise AppError(400, "UNKNOWN_PLOT_TYPE", f"Type de graphique 3D inconnu : {req.plot_type}")

    if sampled:
        note_sampling(fig, total_rows)
    return fig


# --------------------------------------------------------------------------
# Multi-séries à double axe Y (Phase 10)
# --------------------------------------------------------------------------

def _axis_title(series: list, side: str) -> str:
    """Titre d'axe déduit des séries qui y sont rattachées.

    Une seule série sur l'axe -> son nom. Plusieurs -> jointes par une virgule,
    ce qui reste plus lisible qu'un générique "Valeur" dès que l'utilisateur a
    donné des noms explicites à ses séries.
    """
    names = [s.name or s.y_column for s in series if s.y_axis == side]
    return ", ".join(names) if names else ("Valeur" if side == "left" else "")


def build_multi_series_figure(df: pd.DataFrame, req: MultiSeriesPlotRequest) -> go.Figure:
    """Un graphique, plusieurs séries Y, avec axe Y secondaire optionnel.

    Chaque série choisit indépendamment sa colonne Y, son type de trace et son
    axe (gauche/droite) : c'est ce qui permet de superposer par exemple un
    chiffre d'affaires (échelle €) et un nombre d'unités vendues (échelle
    entière bien plus petite) sur un même graphique sans que l'une écrase
    visuellement l'autre.
    """
    _require_columns(df, [req.x_axis])
    for series in req.series:
        _require_columns(df, [series.y_column])
        _require_numeric(df, series.y_column)

    has_secondary = any(s.y_axis == "right" for s in req.series)
    # La tendance ci-dessous est calculée sur `full_df` : un ajustement doit
    # porter sur toutes les données, seul le tracé des points est échantillonné.
    full_df, total_rows = df, len(df)
    df, sampled = plot_frame(df, "scatter")
    fig = go.Figure()

    for i, series in enumerate(req.series):
        color = series.color or PALETTE[i % len(PALETTE)]
        name = series.name or series.y_column
        yaxis_ref = "y2" if series.y_axis == "right" else "y"
        # Une ligne/aire non triée sur X produit un tracé en zigzag illisible ;
        # un scatter ou un bar n'a pas ce problème (pas de segments reliant les points).
        sub = df.sort_values(by=req.x_axis) if series.plot_type in ("line", "area") else df

        if series.plot_type == "bar":
            fig.add_trace(go.Bar(
                x=sub[req.x_axis], y=sub[series.y_column], name=name,
                marker_color=color, yaxis=yaxis_ref,
            ))
        elif series.plot_type == "area":
            fig.add_trace(go.Scatter(
                x=sub[req.x_axis], y=sub[series.y_column], name=name, mode="lines",
                fill="tozeroy", line=dict(color=color), yaxis=yaxis_ref,
            ))
        elif series.plot_type == "line":
            fig.add_trace(go.Scatter(
                x=sub[req.x_axis], y=sub[series.y_column], name=name, mode="lines",
                line=dict(color=color), yaxis=yaxis_ref,
            ))
        else:  # scatter
            fig.add_trace(go.Scatter(
                x=sub[req.x_axis], y=sub[series.y_column], name=name, mode="markers",
                marker=dict(color=color), yaxis=yaxis_ref,
            ))

    # Courbe de tendance (Phase 10.1) : les options avancées s'appliquent
    # désormais aussi au mode multi-séries. La tendance porte sur la première
    # série tracée sur l'axe de gauche — celle que l'œil lit comme principale.
    trend = getattr(req, "trend", None)
    if trend is not None and trend.type != "none":
        from app.plotting_service import _add_trend_traces, compute_trend

        primary = next((s for s in req.series if s.y_axis == "left"), req.series[0])
        pair = full_df[[req.x_axis, primary.y_column]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(pair) >= 3:
            result = compute_trend(
                pair[req.x_axis].to_numpy(dtype=float),
                pair[primary.y_column].to_numpy(dtype=float),
                trend, req.x_axis, primary.y_column,
            )
            if result:
                _add_trend_traces(fig, result, PALETTE[3 % len(PALETTE)], trend.show_equation)

    layout: dict = {
        "title": _default_title(f"{req.x_axis} — {len(req.series)} série(s)", req.title),
        "xaxis": {"title": req.x_axis},
        "yaxis": {"title": _axis_title(req.series, "left")},
        "legend": {"orientation": "h", "y": -0.2},
    }
    if has_secondary:
        layout["yaxis2"] = {
            "title": _axis_title(req.series, "right"),
            "overlaying": "y",
            "side": "right",
        }
    fig.update_layout(**layout)
    _apply_common_style(fig, getattr(req, "style", None))
    if sampled:
        note_sampling(fig, total_rows)
    return fig


def _apply_common_style(fig: go.Figure, style) -> None:
    """Options de présentation communes aux modes multi-séries et sous-graphiques.

    Le mode « graphique simple » passe par `plotting_service.apply_style`, qui
    gère en plus les axes, les échelles et les annotations d'une figure unique.
    Ici, seules les options qui gardent un sens sur une figure à plusieurs
    axes ou à plusieurs cases sont appliquées : imposer un titre d'axe Y unique
    à une grille 3x3 n'en aurait aucun.
    """
    if style is None:
        return
    layout: dict = {
        "showlegend": style.legend_position != "none",
        "template": {"light": "plotly_white", "dark": "plotly_dark"}.get(style.theme, "none"),
    }
    if style.title:
        layout["title"] = style.title
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=style.grid)
    fig.update_yaxes(showgrid=style.grid)


# --------------------------------------------------------------------------
# Grille de sous-graphiques (Phase 10.1)
# --------------------------------------------------------------------------

# Phase 10.4 : une grille a une taille intrinsèque, contrairement à un
# graphique simple qui épouse son conteneur. Sans ça, une grille 3x2 rendue
# dans les 520 px de l'aperçu (ou les 600 px d'un export) écrasait chaque
# case et superposait titres et axes. Chaque ligne garde donc 500 px, chaque
# colonne au moins 420 px ; l'aperçu, l'export image et le rapport PDF lisent
# ces valeurs sur la figure (`layout.height`, `layout.meta.grid`).
SUBPLOT_ROW_PX = 500
SUBPLOT_COL_PX = 420
SUBPLOT_MIN_HEIGHT = 520  # une seule ligne : même hauteur qu'un graphique simple
SUBPLOT_ROW_GAP_PX = 110  # titre d'axe X d'une ligne + titre de la case suivante


def subplot_grid_size(rows: int, cols: int) -> tuple[int, int]:
    """(largeur minimale, hauteur) en pixels d'une grille rows x cols."""
    return SUBPLOT_COL_PX * cols, max(SUBPLOT_MIN_HEIGHT, SUBPLOT_ROW_PX * rows)


def intrinsic_size(fig: go.Figure, default_width: int, default_height: int) -> tuple[int, int]:
    """Taille de rendu d'une figure : jamais plus petite que ce qu'elle déclare.

    Une grille impose sa hauteur et une largeur minimale ; un graphique simple
    ne déclare rien et prend les valeurs demandées.
    """
    meta = fig.layout.meta if isinstance(fig.layout.meta, dict) else {}
    min_width = int((meta.get("grid") or {}).get("min_width") or 0)
    return max(default_width, min_width), max(default_height, int(fig.layout.height or 0))

def _subplot_trace(df: pd.DataFrame, spec, color: str):
    """Trace unique d'une case de la grille, selon son type."""
    if spec.plot_type in ("histogram", "box", "violin"):
        # Ces types ne décrivent qu'une seule variable : Y s'il est renseigné,
        # X sinon, pour que l'utilisateur n'ait pas à deviner lequel remplir.
        column = spec.y or spec.x
        if not column:
            raise AppError(400, "MISSING_COLUMN", "Chaque sous-graphique doit désigner une colonne.")
        _require_columns(df, [column])
        _require_numeric(df, column)
        values = _numeric_series(df, column)
        if spec.plot_type == "histogram":
            return go.Histogram(x=values, name=column, marker_color=color)
        if spec.plot_type == "box":
            return go.Box(y=values, name=column, marker_color=color)
        return go.Violin(y=values, name=column, marker_color=color, box_visible=True, meanline_visible=True)

    if not spec.x or not spec.y:
        raise AppError(400, "MISSING_AXIS", "Un sous-graphique X/Y demande une colonne X et une colonne Y.")
    _require_columns(df, [spec.x, spec.y])
    _require_numeric(df, spec.y)

    if spec.plot_type == "bar":
        # Un bar chart agrège : tracer une barre par ligne empilerait des
        # millions de barres au même endroit — illisible, et plusieurs dizaines
        # de mégaoctets de JSON pour un résultat que l'œil lit comme une seule
        # barre. La moyenne par modalité est ce qu'on attend d'un tel graphique.
        grouped = df.groupby(spec.x, dropna=True)[spec.y].mean().head(MAX_CATEGORIES)
        return go.Bar(x=grouped.index.tolist(), y=grouped.to_numpy().tolist(),
                      name=f"Moyenne de {spec.y}", marker_color=color)

    ordered = df.sort_values(by=spec.x) if spec.plot_type in ("line", "area") else df
    if spec.plot_type == "area":
        return go.Scatter(x=ordered[spec.x], y=ordered[spec.y], name=spec.y, mode="lines",
                          fill="tozeroy", line=dict(color=color))
    if spec.plot_type == "line":
        return go.Scatter(x=ordered[spec.x], y=ordered[spec.y], name=spec.y, mode="lines",
                          line=dict(color=color))
    return go.Scatter(x=ordered[spec.x], y=ordered[spec.y], name=spec.y, mode="markers",
                      marker=dict(color=color))


def build_subplot_figure(df: pd.DataFrame, req) -> go.Figure:
    """Grille de sous-graphiques indépendants (2x2, 3x3, …).

    Chaque case a ses propres colonnes et son propre type : c'est ce qui
    distingue ce mode du multi-séries, où toutes les séries partagent l'axe X.
    """
    if len(req.subplots) > req.rows * req.cols:
        raise AppError(
            400, "TOO_MANY_SUBPLOTS",
            f"{len(req.subplots)} sous-graphiques ne tiennent pas dans une grille {req.rows}x{req.cols}.",
        )

    titles = [spec.title or f"Graphique {i + 1}" for i, spec in enumerate(req.subplots)]
    min_width, height = subplot_grid_size(req.rows, req.cols)
    # L'espacement Plotly est une fraction de la hauteur : avec des lignes de
    # 500 px, la valeur par défaut (0.3 / rows) creuserait 150 px de vide entre
    # deux lignes. 110 px suffisent au titre d'axe X et au titre de la case
    # suivante.
    fig = make_subplots(
        rows=req.rows, cols=req.cols, subplot_titles=titles,
        vertical_spacing=SUBPLOT_ROW_GAP_PX / height if req.rows > 1 else 0,
    )

    sampled_any = False
    for index, spec in enumerate(req.subplots):
        color = spec.color or PALETTE[index % len(PALETTE)]
        case_df, case_sampled = plot_frame(df, spec.plot_type)
        sampled_any = sampled_any or case_sampled
        trace = _subplot_trace(case_df, spec, color)
        fig.add_trace(trace, row=index // req.cols + 1, col=index % req.cols + 1)
        if spec.x and spec.plot_type not in ("histogram", "box", "violin"):
            fig.update_xaxes(title_text=spec.x, row=index // req.cols + 1, col=index % req.cols + 1)
        if spec.y:
            fig.update_yaxes(title_text=spec.y, row=index // req.cols + 1, col=index % req.cols + 1)

    fig.update_layout(
        title=req.title or f"Grille {req.rows}x{req.cols}",
        showlegend=False,  # chaque case porte déjà son titre : la légende ferait doublon
        # `height` seul : Plotly respecte une hauteur déclarée mais continue
        # d'adapter la largeur au conteneur (autosize) ; la largeur minimale
        # passe par `meta` pour que le conteneur puisse défiler horizontalement.
        height=height,
        meta={"grid": {"rows": req.rows, "cols": req.cols, "min_width": min_width}},
    )
    _apply_common_style(fig, getattr(req, "style", None))
    if sampled_any:
        note_sampling(fig, len(df))
    return fig
