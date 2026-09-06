"""Visualisations avancées (Phase 8).

Les ajustements sont confrontés à des références indépendantes (numpy, scipy,
et une implémentation naïve de LOWESS) plutôt qu'à leurs propres résultats.
"""
import io

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from scipy import stats as sps

from app.main import app
from app.plotting_service import lowess, simulate_color

client = TestClient(app)


def _upload(df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    resp = client.post("/api/upload", files={"file": ("data.csv", buf.getvalue().encode(), "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def _dataset() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 180
    x = np.linspace(0, 10, n)
    return pd.DataFrame({
        "x": x,
        "y": 3.0 * x + 2.0 + rng.normal(0, 1.5, n),
        "curved": 0.5 * x ** 2 - 2 * x + 1 + rng.normal(0, 1.0, n),
        "size": rng.uniform(1, 10, n),
        "group": np.repeat(["a", "b", "c"], n // 3),
    })


@pytest.fixture()
def dataset():
    df = _dataset()
    return df, _upload(df)


def _plot(session_id, **kwargs):
    return client.post("/api/plot/advanced", json={"session_id": session_id, **kwargs})


# --- Tendances --------------------------------------------------------------

def test_linear_trend_matches_scipy(dataset):
    df, session_id = dataset
    body = _plot(session_id, plot_type="scatter", x="x", y="y",
                 trend={"type": "linear", "confidence": "95"}).json()
    trend = body["trend"]
    reference = sps.linregress(df["x"], df["y"])
    assert trend["r2"] == pytest.approx(reference.rvalue ** 2, rel=1e-6)
    assert f"{reference.slope:.4g}" in trend["equation"]
    assert trend["n"] == len(df)
    assert trend["confidence_level"] == 0.95
    # Bande de confiance = une trace remplie en plus de la courbe.
    names = [t.get("name") for t in body["figure"]["data"]]
    assert "IC 95 %" in names


def test_polynomial_trend_matches_numpy(dataset):
    df, session_id = dataset
    trend = _plot(session_id, plot_type="scatter", x="x", y="curved",
                  trend={"type": "polynomial", "degree": 2}).json()["trend"]
    # numpy renvoie les coefficients par puissances décroissantes.
    expected = np.polyfit(df["x"], df["curved"], 2)[::-1]
    for coefficient in expected:
        assert f"{coefficient:.4g}".lstrip("-") in trend["equation"].replace("+", "").replace("-", "")
    fitted = np.polyval(np.polyfit(df["x"], df["curved"], 2), df["x"])
    ss_res = float(((df["curved"] - fitted) ** 2).sum())
    ss_tot = float(((df["curved"] - df["curved"].mean()) ** 2).sum())
    assert trend["r2"] == pytest.approx(1 - ss_res / ss_tot, rel=1e-8)


def test_polynomial_beats_linear_on_curved_data(dataset):
    _, session_id = dataset
    linear = _plot(session_id, plot_type="scatter", x="x", y="curved",
                   trend={"type": "linear"}).json()["trend"]
    quadratic = _plot(session_id, plot_type="scatter", x="x", y="curved",
                      trend={"type": "polynomial", "degree": 2}).json()["trend"]
    assert quadratic["r2"] > linear["r2"] + 0.1
    assert quadratic["rmse"] < linear["rmse"]


def test_lowess_matches_naive_implementation():
    """La version vectorisée doit donner exactement la même courbe que la boucle."""
    rng = np.random.default_rng(5)
    x = np.sort(rng.uniform(0, 10, 120))
    y = np.sin(x) + rng.normal(0, 0.2, 120)
    frac, n_out = 0.4, 25
    grid, fitted = lowess(x, y, frac, n_out=n_out)

    span = int(np.ceil(frac * x.size))
    naive = []
    for x0 in grid:
        distance = np.abs(x - x0)
        bandwidth = np.sort(distance)[span - 1]
        weights = (1 - np.clip(distance / bandwidth, 0, 1) ** 3) ** 3
        mean_x = np.average(x, weights=weights)
        mean_y = np.average(y, weights=weights)
        s_xx = np.sum(weights * (x - mean_x) ** 2)
        slope = np.sum(weights * (x - mean_x) * (y - mean_y)) / s_xx
        naive.append(mean_y + slope * (x0 - mean_x))
    assert np.allclose(fitted, naive, rtol=1e-10)


def test_lowess_tracks_nonlinear_shape():
    rng = np.random.default_rng(6)
    x = np.sort(rng.uniform(0, 10, 300))
    df = pd.DataFrame({"x": x, "y": np.sin(x) * 5 + rng.normal(0, 0.4, 300)})
    session_id = _upload(df)
    linear = _plot(session_id, plot_type="scatter", x="x", y="y", trend={"type": "linear"}).json()["trend"]
    smooth = _plot(session_id, plot_type="scatter", x="x", y="y",
                   trend={"type": "lowess", "frac": 0.2}).json()["trend"]
    # Une droite ne peut pas suivre une sinusoïde ; LOWESS le doit.
    assert linear["r2"] < 0.2
    assert smooth["r2"] > 0.9
    assert smooth["equation"] is None  # pas de forme analytique


def test_confidence_band_widens_with_level(dataset):
    _, session_id = dataset

    def band_width(level):
        figure = _plot(session_id, plot_type="scatter", x="x", y="y",
                       trend={"type": "linear", "confidence": level}).json()["figure"]
        band = next(t for t in figure["data"] if t.get("name", "").startswith("IC"))
        return max(band["y"]) - min(band["y"])

    assert band_width("99") > band_width("95")


def test_trend_rejected_on_incompatible_plot(dataset):
    _, session_id = dataset
    resp = _plot(session_id, plot_type="box", y="y", trend={"type": "linear"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TREND_NOT_APPLICABLE"


# --- Repères statistiques ---------------------------------------------------

def test_statistical_overlays_are_drawn(dataset):
    _, session_id = dataset
    layout = _plot(session_id, plot_type="scatter", x="x", y="y",
                   overlays={"mean": True, "median": True, "std": True,
                             "std_sigmas": 2, "percentiles": [10, 90]}).json()["figure"]["layout"]
    texts = " ".join(a["text"] for a in layout.get("annotations", []))
    assert "moyenne" in texts and "médiane" in texts and "P10" in texts and "P90" in texts
    # 2 lignes (moyenne/médiane) + 2 percentiles + 2 bandes sigma
    assert len(layout.get("shapes", [])) == 6


# --- Palettes et accessibilité ---------------------------------------------

def test_okabe_ito_palette_is_used(dataset):
    _, session_id = dataset
    palette = _plot(session_id, plot_type="scatter", x="x", y="y",
                    style={"palette": "Okabe-Ito"}).json()["palette"]
    assert palette[0] == "#E69F00"


def test_colorblind_simulation_changes_colors(dataset):
    _, session_id = dataset
    normal = _plot(session_id, plot_type="scatter", x="x", y="y", style={"palette": "Default"}).json()["palette"]
    simulated = _plot(session_id, plot_type="scatter", x="x", y="y",
                      style={"palette": "Default", "colorblind_mode": "deuteranopia"}).json()["palette"]
    assert simulated != normal
    assert all(c.startswith("#") and len(c) == 7 for c in simulated)


def test_grayscale_simulation_produces_gray():
    for color in ("#E45756", "#4C78A8", "#54A24B"):
        gray = simulate_color(color, "grayscale")
        assert gray[1:3] == gray[3:5] == gray[5:7]


def test_safe_mode_forces_accessible_palette(dataset):
    _, session_id = dataset
    palette = _plot(session_id, plot_type="scatter", x="x", y="y",
                    style={"palette": "Plasma", "colorblind_mode": "safe"}).json()["palette"]
    assert palette[0] == "#E69F00"


# --- Nouveaux types de graphiques -------------------------------------------

@pytest.mark.parametrize("plot_type,payload", [
    ("violin_swarm", {"y": "y", "group_by": "group"}),
    ("strip", {"y": "y", "group_by": "group"}),
    ("ridge", {"y": "y", "group_by": "group"}),
    ("pair", {"columns": ["x", "y", "curved"]}),
    ("joint", {"x": "x", "y": "y"}),
])
def test_new_plot_types_render(dataset, plot_type, payload):
    _, session_id = dataset
    resp = _plot(session_id, plot_type=plot_type, **payload)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["figure"]["data"]) > 0


def test_violin_swarm_overlays_points_on_each_violin(dataset):
    _, session_id = dataset
    figure = _plot(session_id, plot_type="violin_swarm", y="y", group_by="group").json()["figure"]
    types = [t.get("type") for t in figure["data"]]
    assert types.count("violin") == 3
    assert types.count("scatter") == 3  # un nuage de points par groupe


def test_ridge_requires_several_groups(dataset):
    _, session_id = dataset
    resp = _plot(session_id, plot_type="ridge", y="y")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INSUFFICIENT_GROUPS"


def test_pair_requires_two_numeric_columns(dataset):
    _, session_id = dataset
    resp = _plot(session_id, plot_type="pair", columns=["x"])
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INSUFFICIENT_COLUMNS"


def test_joint_has_scatter_and_two_marginals(dataset):
    _, session_id = dataset
    figure = _plot(session_id, plot_type="joint", x="x", y="y").json()["figure"]
    types = [t.get("type", "scatter") for t in figure["data"]]
    assert types.count("histogram") == 2
    assert "scatter" in types


# --- Style ------------------------------------------------------------------

def test_style_options_applied(dataset):
    _, session_id = dataset
    layout = _plot(session_id, plot_type="scatter", x="x", y="y", style={
        "title": "Mon titre", "subtitle": "sous-titre", "x_label": "Axe X", "y_label": "Axe Y",
        "grid": False, "legend_position": "bottom-left", "theme": "dark",
    }).json()["figure"]["layout"]
    assert "Mon titre" in layout["title"]["text"]
    assert "sous-titre" in layout["title"]["text"]
    assert layout["xaxis"]["title"]["text"] == "Axe X"
    assert layout["yaxis"]["title"]["text"] == "Axe Y"
    assert layout["xaxis"]["showgrid"] is False
    assert layout["legend"]["xanchor"] == "left"


def test_custom_annotations_added(dataset):
    _, session_id = dataset
    layout = _plot(session_id, plot_type="scatter", x="x", y="y", style={
        "annotations": [{"text": "point remarquable", "x": 5, "y": 17}],
    }).json()["figure"]["layout"]
    assert any(a["text"] == "point remarquable" for a in layout["annotations"])


def test_log_scale_rejected_on_non_positive_values():
    df = pd.DataFrame({"a": [-3.0, -1.0, 2.0, 5.0, 8.0], "b": [1.0, 2.0, 3.0, 4.0, 5.0]})
    session_id = _upload(df)
    resp = _plot(session_id, plot_type="scatter", x="b", y="a", style={"y_scale": "log"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "LOG_SCALE_INVALID"


def test_advanced_plot_exports_as_png(dataset):
    _, session_id = dataset
    resp = client.post("/api/export/plot", json={
        "session_id": session_id, "kind": "advanced", "format": "png",
        "params": {"plot_type": "scatter", "x": "x", "y": "y", "trend": {"type": "linear"}},
    })
    assert resp.status_code == 200
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_advanced_plot_in_pdf_report(dataset):
    _, session_id = dataset
    resp = client.post("/api/report/pdf", json={
        "session_id": session_id, "sections": ["summary"],
        "plots": [{"kind": "advanced", "title": "Tendance",
                   "params": {"plot_type": "scatter", "x": "x", "y": "y",
                              "trend": {"type": "lowess"}}}],
    })
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
