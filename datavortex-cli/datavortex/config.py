"""Chemins et réglages par défaut du paquet CLI DataVortex."""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["DEFAULT_PORT", "DEFAULT_HOST", "get_default_port", "get_static_dir"]

DEFAULT_PORT = 8000
DEFAULT_HOST = "127.0.0.1"


def get_default_port() -> int:
    """Port par défaut, surchageable via la variable d'environnement DATAVORTEX_PORT."""
    raw = os.environ.get("DATAVORTEX_PORT")
    if not raw:
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def get_static_dir() -> Path:
    """Dossier contenant le frontend React pré-compilé, embarqué dans le paquet."""
    return Path(__file__).parent / "static"
