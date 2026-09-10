"""Tests des opérations en arrière-plan (Phase 9)."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.async_tasks import (
    STATUS_CANCELLED,
    STATUS_DONE,
    STATUS_ERROR,
    Task,
    registry,
)
from app.errors import AppError
from app.main import app

client = TestClient(app)

CSV = (
    b"name,dept,salary\n"
    b"Alice,IT,50000\n"
    b"Bob,Sales,40000\n"
    b"Charlie,IT,60000\n"
    b"Diane,Sales,45000\n"
)


def _session():
    resp = client.post("/api/upload", files={"file": ("t.csv", CSV, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def _await_task(task_id, timeout=15.0):
    """Interroge la route de statut comme le ferait le client, jusqu'au verdict."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/tasks/{task_id}").json()
        if body["status"] in ("done", "error", "cancelled"):
            return body
        time.sleep(0.02)
    pytest.fail(f"La tâche {task_id} n'a pas abouti en {timeout}s")


# --- Registre ------------------------------------------------------------------

def test_task_runs_and_returns_result():
    task = registry.submit("test", lambda a, b: a + b, 2, 3)
    for _ in range(500):
        if task.status == STATUS_DONE:
            break
        time.sleep(0.01)
    assert task.status == STATUS_DONE
    assert task.result == 5
    assert task.duration_seconds() >= 0


def test_task_captures_business_error_code():
    """Un AppError doit garder son code et son statut : c'est ce qui permet au
    client d'afficher « trop de groupes » plutôt que « erreur interne »."""

    def boom():
        raise AppError(422, "TOO_MANY_GROUPS", "Trop de groupes.")

    task = registry.submit("test", boom)
    for _ in range(500):
        if task.status == STATUS_ERROR:
            break
        time.sleep(0.01)
    assert task.status == STATUS_ERROR
    assert task.error_code == "TOO_MANY_GROUPS"
    assert task.http_status == 422
    assert "Trop de groupes" in task.error


def test_task_captures_unexpected_error():
    task = registry.submit("test", lambda: 1 / 0)
    for _ in range(500):
        if task.status == STATUS_ERROR:
            break
        time.sleep(0.01)
    assert task.status == STATUS_ERROR
    assert task.error_code == "ZeroDivisionError"
    assert task.http_status == 500


def test_cancelled_task_discards_its_result():
    started = threading.Event()
    release = threading.Event()

    def slow():
        started.set()
        release.wait(timeout=5)
        return "resultat"

    task = registry.submit("test", slow)
    assert started.wait(timeout=5)
    assert registry.cancel(task.task_id) is True
    release.set()

    for _ in range(500):
        if task.status == STATUS_CANCELLED:
            break
        time.sleep(0.01)
    assert task.status == STATUS_CANCELLED
    assert task.result is None


def test_cancelling_a_finished_task_is_refused():
    task = registry.submit("test", lambda: 42)
    for _ in range(500):
        if task.status == STATUS_DONE:
            break
        time.sleep(0.01)
    assert registry.cancel(task.task_id) is False


def test_cancel_unknown_task_is_false():
    assert registry.cancel("inconnu") is False


def test_registry_stats_count_by_status():
    registry.submit("test", lambda: 1)
    time.sleep(0.2)
    stats = registry.stats()
    assert stats["total"] >= 1
    assert stats.get(STATUS_DONE, 0) >= 1


def test_status_dict_excludes_the_result():
    """Le résultat peut peser lourd : le statut seul doit rester léger."""
    task = Task(task_id="x", kind="groupby")
    task.result = {"rows": list(range(10_000))}
    assert "data" not in task.to_status_dict()
    assert "result" not in task.to_status_dict()


def test_sweep_drops_expired_tasks(monkeypatch):
    import app.async_tasks as module

    task = registry.submit("test", lambda: 1)
    for _ in range(500):
        if task.status == STATUS_DONE:
            break
        time.sleep(0.01)

    monkeypatch.setattr(module, "TASK_TTL_SECONDS", -1)
    registry.submit("test", lambda: 2)  # déclenche le balayage
    assert registry.get(task.task_id) is None


# --- Routes --------------------------------------------------------------------

def test_async_groupby_matches_synchronous_result():
    session_id = _session()
    body = {
        "session_id": session_id,
        "group_by": ["dept"],
        "aggregations": [{"column": "salary", "func": "mean"}],
    }

    sync = client.post("/api/groupby", json=body).json()
    task_id = client.post("/api/groupby/async", json=body).json()["task_id"]
    result = _await_task(task_id)

    assert result["status"] == "done"
    assert result["data"]["rows"] == sync["rows"]
    assert result["data"]["group_count"] == sync["group_count"]


def test_async_groupby_returns_task_id_immediately():
    session_id = _session()
    resp = client.post(
        "/api/groupby/async",
        json={
            "session_id": session_id,
            "group_by": ["dept"],
            "aggregations": [{"column": "salary", "func": "sum"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "groupby"
    assert body["task_id"]
    assert body["status"] in ("pending", "running")


def test_async_groupby_rejects_unknown_session_synchronously():
    """La session est validée avant de créer la tâche : erreur immédiate."""
    resp = client.post(
        "/api/groupby/async",
        json={"session_id": "inconnu", "group_by": ["dept"], "aggregations": []},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_async_groupby_surfaces_business_error_in_task():
    session_id = _session()
    task_id = client.post(
        "/api/groupby/async",
        json={
            "session_id": session_id,
            "group_by": ["dept"],
            "aggregations": [{"column": "name", "func": "mean"}],  # texte : refusé
        },
    ).json()["task_id"]

    result = _await_task(task_id)
    assert result["status"] == "error"
    assert result["error"]["code"] == "INVALID_COLUMN_TYPE"
    assert "numérique" in result["error"]["message"]


def test_task_route_404_for_unknown_id():
    resp = client.get("/api/tasks/inconnu")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_cancel_task_route():
    release = threading.Event()
    started = threading.Event()

    def slow():
        started.set()
        release.wait(timeout=5)
        return "x"

    task = registry.submit("test", slow)
    assert started.wait(timeout=5)
    resp = client.delete(f"/api/tasks/{task.task_id}")
    assert resp.json()["cancelled"] is True
    release.set()


def test_groupby_response_carries_metrics():
    session_id = _session()
    body = client.post(
        "/api/groupby",
        json={
            "session_id": session_id,
            "group_by": ["dept"],
            "aggregations": [{"column": "salary", "func": "mean"}],
        },
    ).json()
    assert body["metrics"]["duration_seconds"] >= 0
    # Le débit se mesure sur les lignes lues (4), pas sur les groupes produits (2).
    assert body["metrics"]["rows_processed"] == 4


def test_health_counts_running_tasks():
    session_id = _session()
    client.post(
        "/api/groupby/async",
        json={
            "session_id": session_id,
            "group_by": ["dept"],
            "aggregations": [{"column": "salary", "func": "mean"}],
        },
    )
    assert client.get("/api/health").json()["tasks"]["total"] >= 1
