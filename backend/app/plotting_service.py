"""Visualisations avancées (Phase 8) : tendances, bandes de confiance, styles.

Ce module complète `app.plotting` (graphiques de base) par ce qu'attend une
figure destinée à un rapport ou une publication : ajustement de tendance avec
son incertitude, repères statistiques, palettes adaptées à la vision des
couleurs, annotations libres et types de graphiques supplémentaires.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats as sps

from app.errors import AppError, column_not_found
from app.models import OverlaySpec, StyleSpec, TrendSpec
from app.parsing import detect_column_type

MAX_CATEGORIES = 20
MAX_PAIR_COLUMNS = 8
MAX_SWARM_POINTS = 2000
LOWESS_GRID = 120
LOWESS_MAX_POINTS = 6000
LOWESS_BOOTSTRAP = 60

# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------

# Okabe-Ito : palette qualitative conçue pour rester discernable avec les
# principales déficiences de la vision des couleurs.
OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]
TOL_BRIGHT = ["#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB"]
DEFAULT_QUALITATIVE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2",
                       "#EECA3B", "#B279A2", "#FF9DA6", "#9D755D", "#BAB0AC"]

QUALITATIVE_PALETTES = {
    "Default": DEFAULT_QUALITATIVE,
    "Okabe-Ito": OKABE_ITO,
    "Tol Bright": TOL_BRIGHT,
    "Viridis": None,   # dérivée de l'échelle continue correspondante
    "Plasma": None,
    "Inferno": None,
    "Cividis": None,
    "Twilight": None,
}

CONTINUOUS_SCALES = {
    "Viridis": "Viridis",
    "Plasma": "Plasma",
    "Inferno": "Inferno",
    "Cividis": "Cividis",
    "Twilight": "Twilight",
    "Default": "Blues",
    "Okabe-Ito": "Cividis",
    "Tol Bright": "Viridis",
}

# Matrices de simulation des déficiences de vision des couleurs
# (approximation linéaire de Viénot, Brettel & Mollon en espace RGB linéaire).
CVD_MATRICES = {
    "deuteranopia": np.array([[0.625, 0.375, 0.0], [0.700, 0.300, 0.0], [0.0, 0.300, 0.700]]),
    "protanopia": np.array([[0.567, 0.433, 0.0], [0.558, 0.442, 0.0], [0.0, 0.242, 0.758]]),
    "tritanopia": np.array([[0.950, 0.050, 0.0], [0.0, 0.433, 0.567], [0.0, 0.475, 0.525]]),
}


def _hex_to_rgb(color: str) -> np.ndarray:
    color = color.lstrip("#")
    return np.array([int(color[i:i + 2], 16) for i in (0, 2, 4)], dtype=float) / 255.0


def _rgb_to_hex(rgb: np.ndarray) -> str:
    clipped = np.clip(rgb, 0.0, 1.0) * 255
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in clipped)


def simulate_color(color: str, mode: str) -> str:
    """Transforme une couleur pour montrer comment elle est perçue en cas de CVD."""
    if mode == "none" or mode not in CVD_MATRICES and mode != "grayscale":
        return color
    rgb = _hex_to_rgb(color)
    if mode == "grayscale":
        # Luminance relative ITU-R BT.709.
        lum = float(np.dot(rgb, [0.2126, 0.7152, 0.0722]))
        return _rgb_to_hex(np.array([lum, lum, lum]))
    return _rgb_to_hex(CVD_MATRICES[mode] @ rgb)


def resolve_palette(style: StyleSpec) -> list[str]:
    """Palette qualitative finale, simulation de CVD comprise."""
    base = QUALITATIVE_PALETTES.get(style.palette)
    if base is None:
        # Les palettes continues (Viridis…) sont échantillonnées en 8 teintes.
        base = _sample_colorscale(CONTINUOUS_SCALES.get(style.palette, "Viridis"), 8)
    if style.colorblind_mode == "none":
        return list(base)
    if style.colorblind_mode == "safe":
        return list(OKABE_ITO)
    return [simulate_color(c, style.colorblind_mode) for c in base]


def _sample_colorscale(name: str, count: int) -> list[str]:
    import plotly.colors as pc

    try:
        scale = pc.get_colorscale(name)
    except Exception:  # pragma: no cover - nom inconnu côté Plotly
        scale = pc.get_colorscale("Viridis")
    positions = np.linspace(0, 1, count)
    sampled = pc.sample_colorscale(scale, list(positions), colortype="rgb")
    out = []
    for rgb_str in sampled:
        nums = [float(v) for v in rgb_str.strip("rgb()").split(",")]
        out.append(_rgb_to_hex(np.array(nums) / 255.0))
    return out


def resolve_colorscale(style: StyleSpec) -> str | list:
    scale_name = CONTINUOUS_SCALES.get(style.palette, "Viridis")
    if style.colorblind_mode in ("none", "safe"):
        return scale_name
    colors = _sample_colorscale(scale_name, 12)
    simulated = [simulate_color(c, style.colorblind_mode) for c in colors]
    return [[i / (len(simulated) - 1), c] for i, c in enumerate(simulated)]


# --------------------------------------------------------------------------
# Helpers colonnes
# --------------------------------------------------------------------------

def _require(df: pd.DataFrame, columns: list[Optional[str]]) -> None:
    for col in columns:
        if col and col not in df.columns:
            raise column_not_found(col)


def _is_numeric(df: pd.DataFrame, col: str) -> bool:
    return detect_column_type(df[col]) in ("integer", "float")


def _require_numeric(df: pd.DataFrame, col: str) -> None:
    if not _is_numeric(df, col):
        raise AppError(400, "INVALID_COLUMN_TYPE",
                       f"La colonne '{col}' doit être numérique pour ce type de graphique.")


def _xy_pairs(df: pd.DataFrame, x: str, y: str) -> tuple[np.ndarray, np.ndarray]:
    pair = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(pair) < 3:
        raise AppError(422, "INSUFFICIENT_DATA",
                       "Au moins 3 points valides sont nécessaires pour ajuster une tendance.")
    return pair[x].to_numpy(dtype=float), pair[y].to_numpy(dtype=float)


# --------------------------------------------------------------------------
# Tendances
# --------------------------------------------------------------------------

def lowess(x: np.ndarray, y: np.ndarray, frac: float, n_out: int = LOWESS_GRID) -> tuple[np.ndarray, np.ndarray]:
    """Régression locale pondérée (LOWESS), version vectorisée.

    Pour chaque point de la grille, on ajuste une droite sur le voisinage le
    plus proche, pondérée par le noyau tricube. Implémentation directe : la
    version de statsmodels est incompatible avec la version de pandas épinglée
    par le projet.
    """
    order = np.argsort(x)
    x, y = x[order], y[order]
    n = x.size
    span = max(2, int(math.ceil(np.clip(frac, 0.05, 1.0) * n)))
    grid = np.linspace(x.min(), x.max(), n_out)

    distances = np.abs(grid[:, None] - x[None, :])          # (n_out, n)
    bandwidth = np.partition(distances, span - 1, axis=1)[:, span - 1]
    bandwidth = np.where(bandwidth <= 0, distances.max(axis=1), bandwidth)
    bandwidth = np.where(bandwidth <= 0, 1.0, bandwidth)

    u = np.clip(distances / bandwidth[:, None], 0.0, 1.0)
    weights = (1.0 - u ** 3) ** 3                            # noyau tricube

    sum_w = weights.sum(axis=1)
    mean_x = (weights * x).sum(axis=1) / sum_w
    mean_y = (weights * y).sum(axis=1) / sum_w
    dx = x[None, :] - mean_x[:, None]
    s_xx = (weights * dx ** 2).sum(axis=1)
    s_xy = (weights * dx * (y[None, :] - mean_y[:, None])).sum(axis=1)
    slope = np.where(s_xx > 1e-12, s_xy / np.where(s_xx > 1e-12, s_xx, 1.0), 0.0)
    fitted = mean_y + slope * (grid - mean_x)
    return grid, fitted


def _polynomial_fit(x: np.ndarray, y: np.ndarray, degree: int, level: Optional[float]) -> dict[str, Any]:
    """Ajustement polynomial par moindres carrés, avec bande de confiance analytique."""
    n = x.size
    n_params = degree + 1
    if n <= n_params:
        raise AppError(422, "INSUFFICIENT_DATA",
                       f"Un polynôme de degré {degree} demande plus de {n_params} points ({n} disponibles).")

    design = np.vander(x, n_params, increasing=True)
    coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ coeffs
    residuals = y - fitted
    dof = n - n_params
    sigma2 = float(residuals @ residuals) / dof if dof > 0 else 0.0

    ss_res = float(residuals @ residuals)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adjusted_r2 = 1.0 - (1.0 - r2) * (n - 1) / dof if dof > 0 else None

    grid = np.linspace(x.min(), x.max(), 200)
    grid_design = np.vander(grid, n_params, increasing=True)
    grid_fit = grid_design @ coeffs

    band = None
    if level is not None and dof > 0 and sigma2 > 0:
        try:
            xtx_inv = np.linalg.pinv(design.T @ design)
            # Variance de la réponse moyenne prédite en chaque point de la grille.
            leverage = np.einsum("ij,jk,ik->i", grid_design, xtx_inv, grid_design)
            std_err = np.sqrt(np.maximum(sigma2 * leverage, 0.0))
            t_crit = float(sps.t.ppf(0.5 + level / 2, df=dof))
            band = (grid_fit - t_crit * std_err, grid_fit + t_crit * std_err)
        except np.linalg.LinAlgError:
            band = None

    return {
        "coefficients": [float(c) for c in coeffs],
        "grid": grid,
        "fitted": grid_fit,
        "band": band,
        "r2": r2,
        "adjusted_r2": adjusted_r2,
        "rmse": math.sqrt(ss_res / n),
        "n": n,
        "dof": dof,
    }


def _format_equation(coeffs: list[float], y_name: str, x_name: str) -> str:
    terms = []
    for power, coef in enumerate(coeffs):
        if power == 0:
            terms.append(f"{coef:.4g}")
        elif power == 1:
            terms.append(f"{coef:+.4g}·{x_name}")
        else:
            terms.append(f"{coef:+.4g}·{x_name}^{power}")
    return f"{y_name} = " + " ".join(terms)


def _lowess_band(x: np.ndarray, y: np.ndarray, frac: float, level: float) -> Optional[tuple]:
    """Bande de confiance LOWESS par bootstrap sur les observations."""
    rng = np.random.default_rng(42)
    n = x.size
    curves = []
    for _ in range(LOWESS_BOOTSTRAP):
        idx = rng.integers(0, n, n)
        try:
            _, fitted = lowess(x[idx], y[idx], frac)
        except (ValueError, FloatingPointError):
            continue
        curves.append(fitted)
    if len(curves) < 10:
        return None
    stacked = np.vstack(curves)
    alpha = (1.0 - level) / 2 * 100
    return np.percentile(stacked, alpha, axis=0), np.percentile(stacked, 100 - alpha, axis=0)


def compute_trend(x: np.ndarray, y: np.ndarray, trend: TrendSpec, x_name: str, y_name: str) -> Optional[dict]:
    """Calcule la courbe de tendance demandée et ses statistiques d'ajustement."""
    if trend.type == "none":
        return None
    level = {"none": None, "95": 0.95, "99": 0.99}[trend.confidence]

    if trend.type in ("linear", "polynomial"):
        degree = 1 if trend.type == "linear" else max(2, min(10, trend.degree))
        fit = _polynomial_fit(x, y, degree, level)
        return {
            "kind": trend.type,
            "grid": fit["grid"],
            "fitted": fit["fitted"],
            "band": fit["band"],
            "level": level,
            "equation": _format_equation(fit["coefficients"], y_name, x_name),
            "r2": fit["r2"],
            "adjusted_r2": fit["adjusted_r2"],
            "rmse": fit["rmse"],
            "n": fit["n"],
        }

    # LOWESS : pas de forme analytique, donc pas d'équation ni de R² paramétrique.
    if x.size > LOWESS_MAX_POINTS:
        rng = np.random.default_rng(42)
        keep = rng.choice(x.size, LOWESS_MAX_POINTS, replace=False)
        x, y = x[keep], y[keep]
    grid, fitted = lowess(x, y, trend.frac)
    band = _lowess_band(x, y, trend.frac, level) if level else None
    # R² local : corrélation entre observations et courbe interpolée.
    interpolated = np.interp(x, grid, fitted)
    ss_res = float(((y - interpolated) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return {
        "kind": "lowess",
        "grid": grid,
        "fitted": fitted,
        "band": band,
        "level": level,
        "equation": None,
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else None,
        "adjusted_r2": None,
        "rmse": math.sqrt(ss_res / x.size),
        "n": int(x.size),
    }


def _add_trend_traces(fig: go.Figure, trend_result: dict, color: str, show_equation: bool) -> None:
    labels = {"linear": "Tendance linéaire", "polynomial": "Tendance polynomiale", "lowess": "LOWESS"}
    if trend_result["band"] is not None:
        low, high = trend_result["band"]
        grid = trend_result["grid"]
        pct = int(trend_result["level"] * 100)
        fig.add_trace(go.Scatter(
            x=np.concatenate([grid, grid[::-1]]),
            y=np.concatenate([high, low[::-1]]),
            fill="toself", fillcolor=_with_alpha(color, 0.18),
            line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip",
            name=f"IC {pct} %", showlegend=True,
        ))
    fig.add_trace(go.Scatter(
        x=trend_result["grid"], y=trend_result["fitted"], mode="lines",
        line=dict(color=color, width=2.5),
        name=labels.get(trend_result["kind"], "Tendance"),
        hovertemplate="%{x:.4g} → %{y:.4g}<extra></extra>",
    ))

    if show_equation:
        parts = []
        if trend_result["equation"]:
            parts.append(trend_result["equation"])
        if trend_result["r2"] is not None:
            parts.append(f"R² = {trend_result['r2']:.4f}")
        parts.append(f"n = {trend_result['n']}")
        fig.add_annotation(
            xref="paper", yref="paper", x=0.02, y=0.98, xanchor="left", yanchor="top",
            text="<br>".join(parts), showarrow=False, align="left",
            bgcolor="rgba(255,255,255,0.75)", bordercolor=color, borderwidth=1, borderpad=4,
            font=dict(size=11),
        )


def _with_alpha(hex_color: str, alpha: float) -> str:
    rgb = _hex_to_rgb(hex_color) * 255
    return f"rgba({int(rgb[0])},{int(rgb[1])},{int(rgb[2])},{alpha})"


# --------------------------------------------------------------------------
# Repères statistiques
# --------------------------------------------------------------------------

def _add_overlays(fig: go.Figure, values: np.ndarray, overlays: OverlaySpec, axis: str) -> None:
    """Ajoute moyenne, médiane, bandes ±σ et percentiles sur l'axe indiqué."""
    if values.size == 0:
        return
    add_line = fig.add_hline if axis == "y" else fig.add_vline
    add_rect = fig.add_hrect if axis == "y" else fig.add_vrect

    mean, std = float(np.mean(values)), float(np.std(values, ddof=1)) if values.size > 1 else 0.0

    if overlays.std and std > 0:
        for k in range(1, max(1, min(3, overlays.std_sigmas)) + 1):
            add_rect(**{
                f"{axis}0": mean - k * std, f"{axis}1": mean + k * std,
                "fillcolor": "#94a3b8", "opacity": 0.10 / k, "line_width": 0, "layer": "below",
            })
    if overlays.mean:
        add_line(**{axis: mean}, line=dict(color="#E45756", dash="dash", width=1.5),
                 annotation_text=f"moyenne = {mean:.4g}", annotation_position="top left")
    if overlays.median:
        add_line(**{axis: float(np.median(values))}, line=dict(color="#54A24B", dash="dot", width=1.5),
                 annotation_text=f"médiane = {np.median(values):.4g}", annotation_position="bottom left")
    for pct in overlays.percentiles:
        if not 0 < pct < 100:
            continue
        value = float(np.percentile(values, pct))
        add_line(**{axis: value}, line=dict(color="#B279A2", dash="dashdot", width=1),
                 annotation_text=f"P{pct:g} = {value:.4g}", annotation_position="top right")


# --------------------------------------------------------------------------
# Style de la figure
# --------------------------------------------------------------------------

LEGEND_POSITIONS = {
    "top-right": dict(x=1, y=1, xanchor="right", yanchor="top"),
    "top-left": dict(x=0, y=1, xanchor="left", yanchor="top"),
    "bottom-right": dict(x=1, y=0, xanchor="right", yanchor="bottom"),
    "bottom-left": dict(x=0, y=0, xanchor="left", yanchor="bottom"),
    "top": dict(x=0.5, y=1.08, xanchor="center", yanchor="bottom", orientation="h"),
    "bottom": dict(x=0.5, y=-0.18, xanchor="center", yanchor="top", orientation="h"),
}


def apply_style(fig: go.Figure, style: StyleSpec, default_title: str,
                x_title: Optional[str], y_title: Optional[str], is_3d: bool = False) -> go.Figure:
    title = style.title or default_title
    if style.subtitle:
        title = f"{title}<br><span style='font-size:0.75em;opacity:0.7'>{style.subtitle}</span>"

    layout: dict[str, Any] = {
        "title": title,
        "showlegend": style.legend_position != "none",
        "template": {"light": "plotly_white", "dark": "plotly_dark"}.get(style.theme, "none"),
    }
    if style.legend_position != "none":
        layout["legend"] = LEGEND_POSITIONS.get(style.legend_position, LEGEND_POSITIONS["top-right"])

    if not is_3d:
        layout["xaxis"] = {
            "title": style.x_label or x_title,
            "showgrid": style.grid,
            "type": style.x_scale,
        }
        layout["yaxis"] = {
            "title": style.y_label or y_title,
            "showgrid": style.grid,
            "type": style.y_scale,
        }

    fig.update_layout(**layout)

    for note in style.annotations:
        fig.add_annotation(
            x=note.x, y=note.y, text=note.text, showarrow=note.arrow,
            arrowhead=2, font=dict(size=note.size),
            bgcolor="rgba(255,255,255,0.7)", bordercolor="#64748b", borderwidth=1, borderpad=3,
        )
    return fig


def _guard_log_scale(style: StyleSpec, series: dict[str, np.ndarray]) -> None:
    """Une échelle log sur des valeurs ≤ 0 produit une figure vide et muette."""
    for axis, values in series.items():
        scale = style.x_scale if axis == "x" else style.y_scale
        if scale == "log" and values.size and float(np.min(values)) <= 0:
            raise AppError(
                422, "LOG_SCALE_INVALID",
                f"L'axe {axis.upper()} contient des valeurs négatives ou nulles : "
                "une échelle logarithmique est impossible.",
            )


# --------------------------------------------------------------------------
# Nouveaux types de graphiques
# --------------------------------------------------------------------------

def _groups(df: pd.DataFrame, column: Optional[str], value_col: str) -> list[tuple[str, np.ndarray]]:
    """Découpe une colonne numérique par modalité, ou renvoie un groupe unique."""
    if not column:
        values = pd.to_numeric(df[value_col], errors="coerce").dropna().to_numpy(dtype=float)
        return [(value_col, values)]
    out = []
    for name, sub in df.groupby(column, dropna=True):
        values = pd.to_numeric(sub[value_col], errors="coerce").dropna().to_numpy(dtype=float)
        if values.size:
            out.append((str(name), values))
    if len(out) > MAX_CATEGORIES:
        raise AppError(
            422, "TOO_MANY_CATEGORIES",
            f"La colonne '{column}' contient {len(out)} modalités (maximum {MAX_CATEGORIES}). "
            "Regroupez les catégories ou choisissez une autre colonne.",
        )
    return out


def _jitter(count: int, width: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-width, width, count)


def _build_violin_swarm(df: pd.DataFrame, req, palette: list[str]) -> go.Figure:
    """Violon (densité) avec les observations individuelles superposées."""
    _require_numeric(df, req.y)
    fig = go.Figure()
    for i, (name, values) in enumerate(_groups(df, req.group_by or req.color_by, req.y)):
        color = palette[i % len(palette)]
        fig.add_trace(go.Violin(
            y=values, name=name, line_color=color, fillcolor=_with_alpha(color, 0.35),
            box_visible=True, meanline_visible=True, points=False, hoverinfo="y",
        ))
        # Le nuage de points est sous-échantillonné : au-delà, il masque le violon.
        shown = values
        if shown.size > MAX_SWARM_POINTS:
            rng = np.random.default_rng(42)
            shown = shown[rng.choice(shown.size, MAX_SWARM_POINTS, replace=False)]
        fig.add_trace(go.Scatter(
            x=np.full(shown.size, i, dtype=float) + _jitter(shown.size, 0.09, seed=i),
            y=shown, mode="markers", showlegend=False,
            marker=dict(color=color, size=4, opacity=0.45, line=dict(width=0)),
            hovertemplate="%{y:.4g}<extra></extra>", xaxis="x2",
        ))
    # Axe secondaire invisible, calé sur les positions des violons.
    fig.update_layout(xaxis2=dict(overlaying="x", range=[-0.5, len(fig.data) / 2 - 0.5],
                                  showticklabels=False, showgrid=False, zeroline=False))
    return fig


def _build_strip(df: pd.DataFrame, req, palette: list[str]) -> go.Figure:
    _require_numeric(df, req.y)
    fig = go.Figure()
    for i, (name, values) in enumerate(_groups(df, req.group_by or req.color_by or req.x, req.y)):
        fig.add_trace(go.Scatter(
            x=np.full(values.size, i, dtype=float) + _jitter(values.size, 0.16, seed=i),
            y=values, mode="markers", name=name,
            marker=dict(color=palette[i % len(palette)], size=6, opacity=0.6),
            hovertemplate=f"{name}<br>%{{y:.4g}}<extra></extra>",
        ))
    labels = [t.name for t in fig.data]
    fig.update_xaxes(tickmode="array", tickvals=list(range(len(labels))), ticktext=labels)
    return fig


def _build_ridge(df: pd.DataFrame, req, palette: list[str]) -> go.Figure:
    """Ridgeline : une densité (KDE) par groupe, décalées verticalement."""
    _require_numeric(df, req.y)
    group_col = req.group_by or req.color_by
    groups = _groups(df, group_col, req.y)
    if len(groups) < 2:
        raise AppError(422, "INSUFFICIENT_GROUPS",
                       "Un ridge plot compare des groupes : choisissez une colonne de groupement "
                       "avec au moins 2 modalités.")

    usable = [(name, values) for name, values in groups if values.size >= 2 and np.unique(values).size >= 2]
    if len(usable) < 2:
        raise AppError(422, "INSUFFICIENT_DATA",
                       "Trop peu de valeurs distinctes par groupe pour estimer une densité.")

    all_values = np.concatenate([v for _, v in usable])
    grid = np.linspace(all_values.min(), all_values.max(), 300)
    densities = []
    for name, values in usable:
        kde = sps.gaussian_kde(values)
        densities.append((name, kde(grid)))

    peak = max(float(d.max()) for _, d in densities) or 1.0
    # Chevauchement partiel : c'est la signature visuelle du ridge plot.
    step = peak / 1.6

    fig = go.Figure()
    for i, (name, density) in enumerate(reversed(densities)):
        offset = i * step
        color = palette[(len(densities) - 1 - i) % len(palette)]
        fig.add_trace(go.Scatter(
            x=grid, y=density + offset, mode="lines", name=name,
            line=dict(color=color, width=1.5), fill="tonexty" if i else "tozeroy",
            fillcolor=_with_alpha(color, 0.55),
            hovertemplate=f"{name}<br>%{{x:.4g}}<extra></extra>",
        ))
    fig.update_yaxes(
        tickmode="array",
        tickvals=[i * step for i in range(len(densities))],
        ticktext=[name for name, _ in reversed(densities)],
    )
    return fig


def _build_pair(df: pd.DataFrame, req, palette: list[str], colorscale) -> go.Figure:
    """Matrice de nuages de points (scatterplot matrix)."""
    columns = req.columns or [c for c in df.columns if _is_numeric(df, c)]
    _require(df, columns)
    numeric = [c for c in columns if _is_numeric(df, c)][:MAX_PAIR_COLUMNS]
    if len(numeric) < 2:
        raise AppError(422, "INSUFFICIENT_COLUMNS",
                       "Un pair plot demande au moins 2 colonnes numériques.")

    dimensions = [dict(label=c, values=df[c]) for c in numeric]
    fig = go.Figure()
    if req.color_by and not _is_numeric(df, req.color_by):
        categories = df[req.color_by].astype(str)
        levels = list(dict.fromkeys(categories.dropna()))
        if len(levels) > MAX_CATEGORIES:
            raise AppError(422, "TOO_MANY_CATEGORIES",
                           f"La colonne '{req.color_by}' a trop de modalités pour colorer un pair plot.")
        codes = categories.map({name: i for i, name in enumerate(levels)})
        fig.add_trace(go.Splom(
            dimensions=dimensions, showupperhalf=False, diagonal=dict(visible=False),
            text=categories,
            marker=dict(color=codes, colorscale=[[i / max(1, len(levels) - 1), palette[i % len(palette)]]
                                                 for i in range(len(levels))],
                        size=4, opacity=0.7, line=dict(width=0)),
            hovertemplate="%{text}<extra></extra>",
        ))
    else:
        marker = dict(size=4, opacity=0.7, line=dict(width=0))
        if req.color_by:
            marker.update(color=df[req.color_by], colorscale=colorscale, showscale=True,
                          colorbar=dict(title=req.color_by, thickness=12))
        else:
            marker.update(color=palette[0])
        fig.add_trace(go.Splom(dimensions=dimensions, showupperhalf=False,
                               diagonal=dict(visible=False), marker=marker))
    return fig


def _build_joint(df: pd.DataFrame, req, palette: list[str], bins: int) -> go.Figure:
    """Nuage de points central entouré des distributions marginales."""
    _require_numeric(df, req.x)
    _require_numeric(df, req.y)
    x, y = _xy_pairs(df, req.x, req.y)

    fig = go.Figure()
    color = palette[0]
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers", name=f"{req.y} vs {req.x}",
        marker=dict(color=color, size=6, opacity=0.6),
        xaxis="x", yaxis="y",
        hovertemplate=f"{req.x} = %{{x:.4g}}<br>{req.y} = %{{y:.4g}}<extra></extra>",
    ))
    fig.add_trace(go.Histogram(
        x=x, nbinsx=bins, marker_color=color, opacity=0.75, showlegend=False,
        xaxis="x", yaxis="y2", hovertemplate="%{x}<br>%{y} obs.<extra></extra>",
    ))
    fig.add_trace(go.Histogram(
        y=y, nbinsy=bins, marker_color=color, opacity=0.75, showlegend=False,
        xaxis="x2", yaxis="y", hovertemplate="%{y}<br>%{x} obs.<extra></extra>",
    ))
    fig.update_layout(
        xaxis=dict(domain=[0, 0.84]),
        yaxis=dict(domain=[0, 0.84]),
        xaxis2=dict(domain=[0.86, 1], showticklabels=False, showgrid=False),
        yaxis2=dict(domain=[0.86, 1], showticklabels=False, showgrid=False),
        bargap=0.05,
    )
    return fig


# --------------------------------------------------------------------------
# Types repris de la Phase 2, enrichis
# --------------------------------------------------------------------------

MAX_SURFACE_CELLS = 2500


def _build_3d(df: pd.DataFrame, req, palette: list[str], colorscale) -> tuple[go.Figure, str, str, str]:
    """Scatter 3D et surface, avec la palette et le style de la Phase 8."""
    if not (req.x and req.y and req.z):
        raise AppError(400, "MISSING_AXIS", "Les colonnes X, Y et Z sont requises pour un graphique 3D.")
    _require(df, [req.x, req.y, req.z, req.color_by])
    for col in (req.x, req.y, req.z):
        _require_numeric(df, col)
    fig = go.Figure()

    if req.plot_type == "surface":
        pivot = df.pivot_table(index=req.y, columns=req.x, values=req.z, aggfunc="mean")
        if pivot.shape[0] * pivot.shape[1] > MAX_SURFACE_CELLS:
            raise AppError(
                422, "GRID_TOO_LARGE",
                "Trop de combinaisons uniques de X/Y pour une surface. Choisissez des colonnes "
                "avec moins de valeurs distinctes, ou passez en scatter 3D.",
            )
        fig.add_trace(go.Surface(z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
                                 colorscale=colorscale))
        title = f"Surface : {req.z} = f({req.x}, {req.y})"
    elif req.color_by and not _is_numeric(df, req.color_by):
        for i, (name, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
            fig.add_trace(go.Scatter3d(x=sub[req.x], y=sub[req.y], z=sub[req.z], mode="markers",
                                       name=str(name),
                                       marker=dict(size=4, color=palette[i % len(palette)])))
        title = f"Scatter 3D : {req.x}, {req.y}, {req.z}"
    else:
        marker = dict(size=4)
        if req.color_by:
            marker.update(color=df[req.color_by], colorscale=colorscale, showscale=True,
                          colorbar=dict(title=req.color_by, thickness=12))
        else:
            marker.update(color=palette[0])
        fig.add_trace(go.Scatter3d(x=df[req.x], y=df[req.y], z=df[req.z], mode="markers", marker=marker))
        title = f"Scatter 3D : {req.x}, {req.y}, {req.z}"

    fig.update_layout(scene=dict(xaxis_title=req.x, yaxis_title=req.y, zaxis_title=req.z))
    return fig, title, "", ""


def _build_classic(df: pd.DataFrame, req, palette: list[str], colorscale) -> tuple[go.Figure, str, str, str]:
    """Reconstruit les graphiques de base avec la palette et les options avancées.

    Renvoie (figure, titre par défaut, titre X, titre Y).
    """
    kind = req.plot_type
    fig = go.Figure()
    bins = max(2, min(200, req.bins))

    if kind == "heatmap":
        columns = req.columns or [c for c in df.columns if _is_numeric(df, c)]
        _require(df, columns)
        numeric = [c for c in columns if _is_numeric(df, c)]
        if len(numeric) < 2:
            raise AppError(422, "INSUFFICIENT_COLUMNS",
                           "Il faut au moins 2 colonnes numériques pour une heatmap de corrélation.")
        corr = df[numeric].corr()
        fig.add_trace(go.Heatmap(
            z=corr.values, x=corr.columns.tolist(), y=corr.columns.tolist(),
            colorscale=colorscale, zmin=-1, zmax=1, zmid=0,
            text=np.round(corr.values, 2), texttemplate="%{text}",
        ))
        return fig, "Heatmap de corrélation", "", ""

    if kind in ("scatter3d", "surface"):
        return _build_3d(df, req, palette, colorscale)

    if kind in ("bar", "pie"):
        if not req.x:
            raise AppError(400, "MISSING_AXIS", "Une colonne est requise pour ce type de graphique.")
        _require(df, [req.x])
        counts = df[req.x].dropna().astype(str).value_counts().head(MAX_CATEGORIES)
        if kind == "bar":
            fig.add_trace(go.Bar(x=counts.index.tolist(), y=counts.values.tolist(),
                                 marker_color=palette[0]))
            return fig, f"Répartition de {req.x}", req.x, "Nombre"
        fig.add_trace(go.Pie(labels=counts.index.tolist(), values=counts.values.tolist(),
                             marker=dict(colors=palette)))
        return fig, f"Répartition de {req.x}", "", ""

    if kind in ("histogram", "kde", "box", "violin"):
        column = req.y or req.x
        if not column:
            raise AppError(400, "MISSING_AXIS", "Une colonne numérique est requise pour ce type de graphique.")
        _require(df, [column, req.group_by])
        _require_numeric(df, column)
        groups = _groups(df, req.group_by, column)

        if kind == "histogram":
            for i, (name, values) in enumerate(groups):
                fig.add_trace(go.Histogram(x=values, name=name, nbinsx=bins,
                                           marker_color=palette[i % len(palette)],
                                           opacity=0.7 if len(groups) > 1 else 1.0))
            if len(groups) > 1:
                fig.update_layout(barmode="overlay")
            return fig, f"Histogramme de {column}", column, "Fréquence"

        if kind == "kde":
            for i, (name, values) in enumerate(groups):
                if np.unique(values).size < 2:
                    continue
                kde = sps.gaussian_kde(values)
                grid = np.linspace(values.min(), values.max(), 250)
                fig.add_trace(go.Scatter(x=grid, y=kde(grid), mode="lines", name=name,
                                         fill="tozeroy", line_color=palette[i % len(palette)],
                                         fillcolor=_with_alpha(palette[i % len(palette)], 0.25)))
            if not fig.data:
                raise AppError(422, "INSUFFICIENT_DATA",
                               "Pas assez de valeurs distinctes pour estimer une densité.")
            return fig, f"Densité (KDE) de {column}", column, "Densité"

        trace_cls = go.Box if kind == "box" else go.Violin
        for i, (name, values) in enumerate(groups):
            extra = {"box_visible": True, "meanline_visible": True} if kind == "violin" else {}
            fig.add_trace(trace_cls(y=values, name=name, marker_color=palette[i % len(palette)], **extra))
        label = "Box plot" if kind == "box" else "Violin plot"
        return fig, f"{label} de {column}", req.group_by or "", column

    # À partir d'ici, tous les types demandent x et y.
    if not req.x or not req.y:
        raise AppError(400, "MISSING_AXIS", "Les colonnes X et Y sont requises pour ce type de graphique.")
    _require(df, [req.x, req.y, req.color_by, req.size_by])

    if kind == "hexbin":
        _require_numeric(df, req.x)
        _require_numeric(df, req.y)
        fig.add_trace(go.Histogram2d(x=df[req.x], y=df[req.y], nbinsx=bins, nbinsy=bins,
                                     colorscale=colorscale))
        return fig, f"Densité 2D : {req.y} vs {req.x}", req.x, req.y

    if kind == "bar_grouped":
        group_col = req.color_by
        if not group_col:
            raise AppError(400, "MISSING_COLOR_BY", "Une colonne de groupement est requise.")
        if group_col == req.x:
            raise AppError(400, "SAME_COLUMN", "Les colonnes X et de groupement doivent être différentes.")
        if _is_numeric(df, req.y):
            agg = df.groupby([req.x, group_col])[req.y].mean().reset_index()
            y_label = f"Moyenne de {req.y}"
        else:
            agg = df.groupby([req.x, group_col]).size().reset_index(name=req.y)
            y_label = "Nombre"
        for i, (name, sub) in enumerate(agg.groupby(group_col)):
            fig.add_trace(go.Bar(x=sub[req.x], y=sub[req.y], name=str(name),
                                 marker_color=palette[i % len(palette)]))
        fig.update_layout(barmode="group")
        return fig, f"{y_label} par {req.x} et {group_col}", req.x, y_label

    if kind == "line":
        _require_numeric(df, req.y)
        if req.color_by:
            for i, (name, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
                ordered = sub.sort_values(by=req.x)
                fig.add_trace(go.Scatter(x=ordered[req.x], y=ordered[req.y], mode="lines",
                                         name=str(name), line=dict(color=palette[i % len(palette)])))
        else:
            ordered = df.sort_values(by=req.x)
            fig.add_trace(go.Scatter(x=ordered[req.x], y=ordered[req.y], mode="lines",
                                     name=req.y, line=dict(color=palette[0])))
        return fig, f"{req.y} en fonction de {req.x}", req.x, req.y

    # scatter / bubble
    _require_numeric(df, req.x)
    _require_numeric(df, req.y)
    sizes = None
    if req.size_by:
        _require_numeric(df, req.size_by)
        raw = pd.to_numeric(df[req.size_by], errors="coerce").fillna(0).to_numpy(dtype=float)
        span = raw.max() - raw.min()
        sizes = np.full_like(raw, 12.0) if span == 0 else 6 + (raw - raw.min()) / span * 24
    elif kind == "bubble":
        raise AppError(400, "MISSING_SIZE_BY", "Le champ « taille par » est requis pour un bubble chart.")

    if req.color_by and not _is_numeric(df, req.color_by):
        for i, (name, sub) in enumerate(df.groupby(req.color_by, dropna=True)):
            marker = dict(color=palette[i % len(palette)], opacity=0.75)
            if sizes is not None:
                marker["size"] = sizes[df[req.color_by].astype(str) == str(name)]
            else:
                marker["size"] = 7
            fig.add_trace(go.Scatter(x=sub[req.x], y=sub[req.y], mode="markers",
                                     name=str(name), marker=marker))
    else:
        marker = dict(size=sizes if sizes is not None else 7, opacity=0.75)
        if req.color_by:
            marker.update(color=df[req.color_by], colorscale=colorscale, showscale=True,
                          colorbar=dict(title=req.color_by, thickness=12))
        else:
            marker.update(color=palette[0])
        fig.add_trace(go.Scatter(x=df[req.x], y=df[req.y], mode="markers",
                                 name=f"{req.y} vs {req.x}", marker=marker))

    suffix = f" (taille : {req.size_by})" if req.size_by else ""
    return fig, f"{req.y} vs {req.x}{suffix}", req.x, req.y


# --------------------------------------------------------------------------
# Point d'entrée
# --------------------------------------------------------------------------

# Types pour lesquels une courbe de tendance sur (x, y) a un sens.
TREND_COMPATIBLE = {"scatter", "line", "bubble", "joint"}
# Types dont l'axe portant la distribution est X (et non Y).
OVERLAY_ON_X = {"histogram", "kde", "ridge"}


def build_advanced_figure(df: pd.DataFrame, req) -> dict[str, Any]:
    """Construit la figure demandée et renvoie ses statistiques d'ajustement."""
    style = req.style
    palette = resolve_palette(style)
    colorscale = resolve_colorscale(style)
    trend_stats = None

    if req.plot_type == "violin_swarm":
        fig, title, x_title, y_title = _build_violin_swarm(df, req, palette), \
            f"Violin + observations : {req.y}", req.group_by or "", req.y
    elif req.plot_type == "strip":
        fig, title, x_title, y_title = _build_strip(df, req, palette), \
            f"Strip plot : {req.y}", req.group_by or req.x or "", req.y
    elif req.plot_type == "ridge":
        fig, title, x_title, y_title = _build_ridge(df, req, palette), \
            f"Ridge plot : {req.y} par {req.group_by or req.color_by}", req.y, ""
    elif req.plot_type == "pair":
        fig = _build_pair(df, req, palette, colorscale)
        title, x_title, y_title = "Pair plot", "", ""
    elif req.plot_type == "joint":
        fig = _build_joint(df, req, palette, max(2, min(200, req.bins)))
        title, x_title, y_title = f"Joint plot : {req.y} vs {req.x}", req.x, req.y
    else:
        fig, title, x_title, y_title = _build_classic(df, req, palette, colorscale)

    # --- Tendance -----------------------------------------------------------
    if req.trend.type != "none":
        if req.plot_type not in TREND_COMPATIBLE:
            raise AppError(
                400, "TREND_NOT_APPLICABLE",
                f"Une courbe de tendance ne s'applique pas à un graphique « {req.plot_type} ». "
                f"Types compatibles : {', '.join(sorted(TREND_COMPATIBLE))}.",
            )
        x_values, y_values = _xy_pairs(df, req.x, req.y)
        result = compute_trend(x_values, y_values, req.trend, req.x, req.y)
        if result:
            _add_trend_traces(fig, result, palette[3 % len(palette)], req.trend.show_equation)
            trend_stats = {
                "type": result["kind"],
                "equation": result["equation"],
                "r2": result["r2"],
                "adjusted_r2": result["adjusted_r2"],
                "rmse": result["rmse"],
                "n": result["n"],
                "confidence_level": result["level"],
            }

    # --- Repères statistiques ----------------------------------------------
    overlays = req.overlays
    if any([overlays.mean, overlays.median, overlays.std, overlays.percentiles]):
        target = req.y if req.y and _is_numeric(df, req.y) else (req.x if req.x and _is_numeric(df, req.x) else None)
        if target:
            values = pd.to_numeric(df[target], errors="coerce").dropna().to_numpy(dtype=float)
            axis = "x" if req.plot_type in OVERLAY_ON_X else "y"
            _add_overlays(fig, values, overlays, axis)

    # --- Style ---------------------------------------------------------------
    if req.x and req.y and _is_numeric(df, req.x) and _is_numeric(df, req.y):
        _guard_log_scale(style, {
            "x": pd.to_numeric(df[req.x], errors="coerce").dropna().to_numpy(dtype=float),
            "y": pd.to_numeric(df[req.y], errors="coerce").dropna().to_numpy(dtype=float),
        })
    is_matrix = req.plot_type in ("pair", "joint", "heatmap", "pie", "scatter3d", "surface")
    apply_style(fig, style, title, x_title, y_title, is_3d=is_matrix)
    if is_matrix:
        # Ces figures gèrent leurs propres axes : on n'impose que le titre.
        fig.update_layout(title=style.title or title)

    return {"figure": fig, "trend": trend_stats, "palette": palette}
