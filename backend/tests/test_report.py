from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV_CONTENT = (
    b"name,age,score,category\n"
    b"Alice,30,85.5,A\n"
    b"Bob,25,90.0,B\n"
    b"Charlie,35,78.2,A\n"
    b"Diana,28,88.0,B\n"
)


def _upload_and_parse():
    resp = client.post("/api/upload", files={"file": ("test.csv", CSV_CONTENT, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def test_report_all_sections():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["summary", "stats", "preview", "plots", "correlations", "metadata"],
            "plots": [{"kind": "1d", "params": {"plot_type": "histogram", "column": "age"}}],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 1000


def test_report_selected_sections_only():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={"session_id": session_id, "sections": ["summary"]},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_no_sections_still_has_cover():
    session_id = _upload_and_parse()
    resp = client.post("/api/report/pdf", json={"session_id": session_id, "sections": []})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_with_two_plots():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["plots"],
            "plots": [
                {"kind": "1d", "params": {"plot_type": "histogram", "column": "age"}},
                {"kind": "2d", "params": {"plot_type": "scatter", "x": "age", "y": "score"}},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_reflects_active_filter():
    session_id = _upload_and_parse()
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "category", "operator": "eq", "value": "A"}},
    )
    resp = client.post(
        "/api/report/pdf",
        json={"session_id": session_id, "sections": ["summary"]},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_page_format_and_orientation():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["summary"],
            "page_format": "Letter",
            "orientation": "landscape",
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_session_not_found():
    resp = client.post("/api/report/pdf", json={"session_id": "nope", "sections": ["summary"]})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_report_invalid_plot_params_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["plots"],
            "plots": [{"kind": "2d", "params": {"plot_type": "scatter", "x": "does_not_exist", "y": "score"}}],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COLUMN_NOT_FOUND"
