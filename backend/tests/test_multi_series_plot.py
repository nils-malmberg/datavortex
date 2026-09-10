"""Phase 10 : graphiques multi-séries avec axe Y secondaire."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV_CONTENT = (
    b"date,revenue,units,margin\n"
    b"2024-01,1000,50,0.20\n"
    b"2024-02,1200,55,0.22\n"
    b"2024-03,900,40,0.18\n"
    b"2024-04,1500,70,0.25\n"
)


def _upload_and_parse():
    resp = client.post("/api/upload", files={"file": ("sales.csv", CSV_CONTENT, "text/csv")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    return session_id


def test_single_series_no_secondary_axis():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "title": "Revenue",
            "x_axis": "date",
            "series": [{"y_column": "revenue", "plot_type": "line"}],
        },
    )
    assert resp.status_code == 200
    figure = resp.json()["figure"]
    assert len(figure["data"]) == 1
    assert "yaxis2" not in figure["layout"]


def test_dual_axis_two_series():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "title": "Sales Analysis",
            "x_axis": "date",
            "series": [
                {"y_column": "revenue", "y_axis": "left", "plot_type": "line", "name": "Revenue"},
                {"y_column": "units", "y_axis": "right", "plot_type": "bar", "name": "Units"},
            ],
        },
    )
    assert resp.status_code == 200
    figure = resp.json()["figure"]
    assert len(figure["data"]) == 2
    assert "yaxis2" in figure["layout"]
    assert figure["layout"]["yaxis2"]["side"] == "right"
    assert figure["layout"]["yaxis2"]["overlaying"] == "y"
    # La trace routée à droite porte bien la référence d'axe attendue.
    bar_trace = next(t for t in figure["data"] if t["type"] == "bar")
    assert bar_trace["yaxis"] == "y2"


def test_three_series_mixed_axes_and_types():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "x_axis": "date",
            "series": [
                {"y_column": "revenue", "y_axis": "left", "plot_type": "line"},
                {"y_column": "units", "y_axis": "right", "plot_type": "bar"},
                {"y_column": "margin", "y_axis": "left", "plot_type": "scatter"},
            ],
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["figure"]["data"]) == 3


def test_area_plot_type():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "x_axis": "date",
            "series": [{"y_column": "revenue", "plot_type": "area"}],
        },
    )
    assert resp.status_code == 200
    trace = resp.json()["figure"]["data"][0]
    assert trace["fill"] == "tozeroy"


def test_custom_series_name_and_color_applied():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "x_axis": "date",
            "series": [{"y_column": "revenue", "name": "CA total", "color": "#ff0000"}],
        },
    )
    assert resp.status_code == 200
    trace = resp.json()["figure"]["data"][0]
    assert trace["name"] == "CA total"
    assert trace["marker"]["color"] == "#ff0000"


def test_missing_x_axis_column_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={"session_id": session_id, "x_axis": "nope", "series": [{"y_column": "revenue"}]},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COLUMN_NOT_FOUND"


def test_non_numeric_series_column_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={"session_id": session_id, "x_axis": "date", "series": [{"y_column": "date"}]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_COLUMN_TYPE"


def test_empty_series_list_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={"session_id": session_id, "x_axis": "date", "series": []},
    )
    assert resp.status_code == 422  # validation Pydantic (min_length=1)


def test_too_many_series_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/multi-series",
        json={
            "session_id": session_id,
            "x_axis": "date",
            "series": [{"y_column": "revenue"} for _ in range(11)],
        },
    )
    assert resp.status_code == 422  # validation Pydantic (max_length=10)


def test_session_not_found():
    resp = client.post(
        "/api/plot/multi-series",
        json={"session_id": "nonexistent", "x_axis": "date", "series": [{"y_column": "revenue"}]},
    )
    assert resp.status_code == 404
