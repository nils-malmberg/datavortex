"""Phase 10.1 : grille de sous-graphiques et options avancées multi-modes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV_CONTENT = (
    b"date,revenue,units,margin,region\n"
    b"2024-01,1000,50,0.20,Nord\n"
    b"2024-02,1200,55,0.22,Sud\n"
    b"2024-03,900,40,0.18,Nord\n"
    b"2024-04,1500,70,0.25,Sud\n"
    b"2024-05,1100,52,0.21,Est\n"
)


def _session():
    resp = client.post("/api/upload", files={"file": ("sales.csv", CSV_CONTENT, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def _subplots(session_id, **overrides):
    body = {
        "session_id": session_id,
        "rows": 2,
        "cols": 2,
        "subplots": [
            {"plot_type": "scatter", "x": "revenue", "y": "units"},
            {"plot_type": "line", "x": "revenue", "y": "margin"},
            {"plot_type": "histogram", "y": "revenue"},
            {"plot_type": "box", "y": "units"},
        ],
    }
    body.update(overrides)
    return client.post("/api/plot/subplots", json=body)


def test_grid_creates_one_trace_and_one_axis_pair_per_cell():
    resp = _subplots(_session())
    assert resp.status_code == 200
    figure = resp.json()["figure"]
    assert len(figure["data"]) == 4
    assert len([k for k in figure["layout"] if k.startswith("xaxis")]) == 4


def test_grid_places_cells_row_major():
    """La case n occupe la ligne n//cols et la colonne n%cols."""
    resp = _subplots(_session(), rows=2, cols=2)
    figure = resp.json()["figure"]
    # Plotly nomme les axes x, x2, x3, x4 dans l'ordre d'ajout des cases.
    axes = [trace.get("xaxis", "x") for trace in figure["data"]]
    assert axes == ["x", "x2", "x3", "x4"]


@pytest.mark.parametrize("rows,cols", [(1, 2), (2, 3), (3, 3), (4, 2)])
def test_grid_presets_supported(rows, cols):
    subplots = [{"plot_type": "scatter", "x": "revenue", "y": "units"} for _ in range(rows * cols)]
    resp = _subplots(_session(), rows=rows, cols=cols, subplots=subplots)
    assert resp.status_code == 200
    assert len(resp.json()["figure"]["data"]) == rows * cols


def test_single_variable_types_need_no_x():
    resp = _subplots(
        _session(),
        rows=1, cols=3,
        subplots=[
            {"plot_type": "histogram", "y": "revenue"},
            {"plot_type": "box", "y": "units"},
            {"plot_type": "violin", "y": "margin"},
        ],
    )
    assert resp.status_code == 200
    assert [t["type"] for t in resp.json()["figure"]["data"]] == ["histogram", "box", "violin"]


def test_subplot_bar_aggregates_by_category():
    """Un bar chart agrège par modalité au lieu d'émettre une barre par ligne."""
    resp = _subplots(
        _session(), rows=1, cols=1,
        subplots=[{"plot_type": "bar", "x": "region", "y": "revenue"}],
    )
    assert resp.status_code == 200
    trace = resp.json()["figure"]["data"][0]
    assert sorted(trace["x"]) == ["Est", "Nord", "Sud"]  # 3 modalités, pas 5 lignes


def test_more_subplots_than_cells_rejected():
    subplots = [{"plot_type": "scatter", "x": "revenue", "y": "units"} for _ in range(5)]
    resp = _subplots(_session(), rows=2, cols=2, subplots=subplots)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "TOO_MANY_SUBPLOTS"


def test_subplot_missing_axis_rejected():
    resp = _subplots(_session(), rows=1, cols=1, subplots=[{"plot_type": "scatter", "y": "units"}])
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_AXIS"


def test_grid_larger_than_max_rejected():
    resp = _subplots(_session(), rows=5, cols=5)
    assert resp.status_code == 422  # borne Pydantic


def test_grid_style_options_applied():
    resp = _subplots(_session(), style={"theme": "dark", "grid": False, "legend_position": "none"})
    assert resp.status_code == 200
    layout = resp.json()["figure"]["layout"]
    assert layout["showlegend"] is False
    assert layout["template"]["layout"]["paper_bgcolor"] == "rgb(17,17,17)"


def test_multi_series_supports_trend_and_style():
    """Les options avancées ne sont plus réservées au mode simple."""
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": _session(),
            "x_axis": "revenue",
            "series": [{"y_column": "units", "y_axis": "left", "plot_type": "scatter"}],
            "trend": {"type": "linear", "confidence": "95", "degree": 2, "frac": 0.35, "show_equation": True},
            "style": {"theme": "dark", "grid": False, "legend_position": "bottom", "title": "Avec tendance"},
        },
    )
    assert resp.status_code == 200
    figure = resp.json()["figure"]
    # Série + courbe de tendance + bande de confiance.
    assert len(figure["data"]) > 1
    assert figure["layout"]["title"]["text"] == "Avec tendance"


def test_subplots_exportable_as_png():
    resp = client.post(
        "/api/export/plot",
        json={
            "session_id": _session(),
            "kind": "subplots",
            "format": "png",
            "params": {
                "rows": 1, "cols": 2,
                "subplots": [
                    {"plot_type": "scatter", "x": "revenue", "y": "units"},
                    {"plot_type": "box", "y": "margin"},
                ],
            },
        },
    )
    assert resp.status_code == 200
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_subplots_can_go_into_a_pdf_report():
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": _session(),
            "sections": ["plots"],
            "plots": [{
                "kind": "subplots",
                "title": "Vue d'ensemble",
                "params": {
                    "rows": 1, "cols": 2,
                    "subplots": [
                        {"plot_type": "scatter", "x": "revenue", "y": "units"},
                        {"plot_type": "histogram", "y": "margin"},
                    ],
                },
            }],
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
