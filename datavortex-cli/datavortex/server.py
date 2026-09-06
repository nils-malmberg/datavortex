"""Démarrage du serveur DataVortex packagé : API FastAPI + frontend React statique.

En développement, l'API (uvicorn, port 8000) et le frontend (vite, port 5173)
tournent séparément avec un proxy `/api`. En distribution CLI, il n'y a
qu'un seul process : le frontend pré-compilé (`datavortex/static/`, copié
depuis `frontend/dist/` au moment du build) est servi par la même appli
FastAPI que l'API, sur le même port.
"""
from __future__ import annotations

from pathlib import Path

import uvicorn
from app.main import app as fastapi_app
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_static_dir


def mount_frontend(app: FastAPI, static_dir: Path) -> bool:
    """Monte le frontend pré-compilé sur `app`, si présent. Retourne True si monté.

    Sans frontend pré-compilé (ex. environnement de dev du backend seul),
    l'API reste utilisable, seule l'UI est absente — ce n'est pas une erreur.
    Montée en dernier : les routes /api/* déjà enregistrées par app.main
    restent prioritaires, ce montage ne capte que ce qu'elles ne gèrent pas.
    """
    if not (static_dir / "index.html").exists():
        return False
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return True


mount_frontend(fastapi_app, get_static_dir())


def start_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")
