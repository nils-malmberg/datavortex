from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV_CONTENT = b"name,age,score\nAlice,30,85.5\nBob,25,90.0\nCharlie,35,78.2\n"


def _upload_and_parse():
    resp = client.post("/api/upload", files={"file": ("test.csv", CSV_CONTENT, "text/csv")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    return session_id


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_and_parse():
    resp = client.post("/api/upload", files={"file": ("test.csv", CSV_CONTENT, "text/csv")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detected_separator"] == ","
    session_id = body["session_id"]

    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    assert resp.json()["n_rows"] == 3


def test_preview():
    session_id = _upload_and_parse()
    resp = client.get(f"/api/data/{session_id}/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] == 3
    assert data["columns"] == ["name", "age", "score"]


def test_stats():
    session_id = _upload_and_parse()
    resp = client.get(f"/api/stats/{session_id}")
    assert resp.status_code == 200
    assert "age" in resp.json()["columns"]


def test_filter():
    session_id = _upload_and_parse()
    resp = client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "age", "operator": "gt", "value": 26}},
    )
    assert resp.status_code == 200
    assert resp.json()["total_rows"] == 2

    # reset
    resp = client.post(f"/api/data/{session_id}/filter", json={"filter": None})
    assert resp.status_code == 200
    assert resp.json()["total_rows"] == 3


def test_create_column():
    session_id = _upload_and_parse()
    resp = client.post(
        f"/api/data/{session_id}/columns",
        json={"name": "double_age", "formula": "{age} * 2"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "double_age" in body["columns"]
    assert body["preview"][0]["double_age"] == 60


def test_create_column_duplicate_name_rejected():
    session_id = _upload_and_parse()
    client.post(f"/api/data/{session_id}/columns", json={"name": "dup", "formula": "{age}"})
    resp = client.post(f"/api/data/{session_id}/columns", json={"name": "dup", "formula": "{age}"})
    assert resp.status_code == 409


def test_plot_1d_histogram():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/1d",
        json={"session_id": session_id, "column": "age", "plot_type": "histogram"},
    )
    assert resp.status_code == 200
    assert "figure" in resp.json()


def test_plot_2d_scatter():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/plot/2d",
        json={"session_id": session_id, "plot_type": "scatter", "x": "age", "y": "score"},
    )
    assert resp.status_code == 200
    assert "figure" in resp.json()


def test_export_csv():
    session_id = _upload_and_parse()
    resp = client.post("/api/export/csv", json={"session_id": session_id, "separator": ";"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Alice" in resp.text
    assert "name;age;score" in resp.text


def test_export_csv_with_filter_comment():
    session_id = _upload_and_parse()
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "age", "operator": "gt", "value": 26}},
    )
    resp = client.post("/api/export/csv", json={"session_id": session_id})
    assert resp.status_code == 200
    assert resp.text.startswith("# Filtre appliqué")
    assert "Alice" not in resp.text or "Bob" not in resp.text  # au moins une ligne exclue par le filtre


def test_export_plot_png():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/export/plot",
        json={
            "session_id": session_id,
            "kind": "1d",
            "format": "png",
            "params": {"column": "age", "plot_type": "histogram"},
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_session_not_found():
    resp = client.get("/api/data/nonexistent/preview")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_wrong_separator_rejected():
    resp = client.post("/api/upload", files={"file": ("test.csv", CSV_CONTENT, "text/csv")})
    session_id = resp.json()["session_id"]
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": "|"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SEPARATOR_LIKELY_WRONG"
