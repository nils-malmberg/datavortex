"""Construction des figures Plotly pour les visualisations 1D/2D/3D (Phase 2)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats as scipy_stats

from app.errors import AppError, column_not_found
from app.models import Plot1DRequest, Plot2DRequest, Plot3DRequest
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

    return fig


# --------------------------------------------------------------------------
# 3D
# --------------------------------------------------------------------------

def build_3d_figure(df: pd.DataFrame, req: Plot3DRequest) -> go.Figure:
    _require_columns(df, [req.x, req.y, req.z, req.color_by])
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

    return fig
