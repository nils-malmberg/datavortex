from fastapi.testclient import TestClient

from app.main import app
from app.session_store import MAX_SESSIONS

client = TestClient(app)

CSV_CONTENT = b"a,b\n1,2\n3,4\n"


def _upload():
    return client.post("/api/upload", files={"file": ("t.csv", CSV_CONTENT, "text/csv")})


def test_sessions_are_isolated():
    resp1 = _upload()
    resp2 = _upload()
    sid1, sid2 = resp1.json()["session_id"], resp2.json()["session_id"]
    assert sid1 != sid2

    client.post("/api/parse", json={"session_id": sid1, "separator": ","})
    client.post("/api/parse", json={"session_id": sid2, "separator": ","})

    client.post(f"/api/data/{sid1}/columns", json={"name": "c", "formula": "{a} * 2"})
    resp = client.get(f"/api/data/{sid2}/preview")
    assert "c" not in resp.json()["columns"]


def test_delete_session():
    resp = _upload()
    session_id = resp.json()["session_id"]
    del_resp = client.delete(f"/api/session/{session_id}")
    assert del_resp.status_code == 200

    resp = client.get(f"/api/data/{session_id}/preview")
    assert resp.status_code == 404


def test_delete_unknown_session_is_idempotent():
    resp = client.delete("/api/session/does-not-exist")
    assert resp.status_code == 200


def test_session_limit_reached():
    for _ in range(MAX_SESSIONS):
        resp = _upload()
        assert resp.status_code == 200
    resp = _upload()
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "SESSION_LIMIT_REACHED"
