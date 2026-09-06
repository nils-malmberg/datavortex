"""Vérifie que le serveur packagé sert l'API *et* le frontend statique
sur le même process, avec les routes /api/* prioritaires sur le fallback
frontend (ordre de montage dans server.py)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from datavortex.server import fastapi_app, mount_frontend


def test_api_routes_still_respond_once_frontend_is_mounted():
    client = TestClient(fastapi_app)
    response = client.get("/api/health")
    assert response.status_code == 200


def test_mount_frontend_returns_false_when_static_dir_missing(tmp_path):
    app = FastAPI()
    routes_before = list(app.routes)
    mounted = mount_frontend(app, tmp_path / "does-not-exist")
    assert mounted is False
    # L'absence de frontend ne doit ajouter aucune route catch-all.
    assert app.routes == routes_before


def test_mount_frontend_serves_index_html(tmp_path):
    (tmp_path / "index.html").write_text("<html>DataVortex</html>")
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    mounted = mount_frontend(app, tmp_path)
    assert mounted is True

    client = TestClient(app)
    # La route API déclarée avant le montage reste prioritaire.
    assert client.get("/api/health").json() == {"status": "ok"}
    # Tout le reste tombe sur le frontend statique.
    index_response = client.get("/")
    assert index_response.status_code == 200
    assert "DataVortex" in index_response.text
