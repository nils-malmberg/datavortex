from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

IRIS_A = b"species,sepal_length,sepal_width\nsetosa,5.1,3.5\nversicolor,6.0,2.9\n"
IRIS_B = b"species,sepal_length,sepal_width\nvirginica,6.5,3.0\nvirginica,6.7,3.1\n"
IRIS_META = b"species,continent\nsetosa,North America\nversicolor,North America\nvirginica,North America\n"
OTHER_SCHEMA = b"name,age\nAlice,30\nBob,25\n"


def _upload_and_parse(content, filename="test.csv"):
    resp = client.post("/api/upload", files={"file": (filename, content, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def test_concat_sums_row_counts():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_b = _upload_and_parse(IRIS_B, "b.csv")
    resp = client.post("/api/merge", json={"session_ids": [sid_a, sid_b], "mode": "concat"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 4
    assert body["column_count"] == 3

    preview = client.get(f"/api/data/{body['new_session_id']}/preview")
    assert preview.json()["total_rows"] == 4


def test_concat_incompatible_columns_rejected():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_other = _upload_and_parse(OTHER_SCHEMA, "other.csv")
    resp = client.post("/api/merge", json={"session_ids": [sid_a, sid_other], "mode": "concat"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INCOMPATIBLE_COLUMNS"


def test_merge_joins_on_key_without_nulls():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_meta = _upload_and_parse(IRIS_META, "meta.csv")
    resp = client.post(
        "/api/merge",
        json={"session_ids": [sid_a, sid_meta], "mode": "merge", "key_column": "species"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 2
    assert "continent" in body["columns"]

    preview = client.get(f"/api/data/{body['new_session_id']}/preview")
    rows = preview.json()["rows"]
    assert all(v is not None for row in rows for v in row.values())


def test_merge_missing_key_column_rejected():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_b = _upload_and_parse(IRIS_B, "b.csv")
    resp = client.post("/api/merge", json={"session_ids": [sid_a, sid_b], "mode": "merge"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_KEY_COLUMN"


def test_merge_key_column_not_found_rejected():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_other = _upload_and_parse(OTHER_SCHEMA, "other.csv")
    resp = client.post(
        "/api/merge",
        json={"session_ids": [sid_a, sid_other], "mode": "merge", "key_column": "species"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "KEY_COLUMN_NOT_FOUND"


def test_merge_requires_at_least_two_sessions():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    resp = client.post("/api/merge", json={"session_ids": [sid_a], "mode": "concat"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INSUFFICIENT_SESSIONS"


def test_merged_session_is_independent_new_session():
    sid_a = _upload_and_parse(IRIS_A, "a.csv")
    sid_b = _upload_and_parse(IRIS_B, "b.csv")
    resp = client.post("/api/merge", json={"session_ids": [sid_a, sid_b], "mode": "concat"})
    new_sid = resp.json()["new_session_id"]
    assert new_sid not in (sid_a, sid_b)

    original = client.get(f"/api/data/{sid_a}/preview")
    assert original.json()["total_rows"] == 2
