"""Le frontend commité dans datavortex/static/ est-il celui du code courant ?

`uv tool install` n'exécute pas Node : il livre static/ tel qu'il est commité.
Entre les Phases 9 et 10.1, le frontend a changé sans que static/ soit
régénéré, et les utilisateurs installaient une interface d'avant. Ces tests
rendent cette dérive visible en CI : ils vérifient que le bundle existe, qu'il
est complet, et qu'il contient des repères des fonctionnalités récentes.
"""
from __future__ import annotations

from pathlib import Path

from datavortex import __version__
from datavortex.config import get_static_dir

STATIC = get_static_dir()

# Chaînes visibles dans l'interface, une par fonctionnalité récente : si l'une
# manque du bundle, c'est que static/ n'a pas été régénéré (./build.sh).
RECENT_UI_MARKERS = {
    "Phase 10.1 — grille de sous-graphiques": "Taille de la grille",
    "Phase 10.1 — sélecteur de disposition": "Multi-séries",
    "Phase 10.2 — séparateur regex": "Motif de séparateur",
    "Phase 10.4 — diagnostic TensorFlow": "Réseau de neurones indisponible sur ce serveur",
}


def _bundle_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in STATIC.rglob("*.js"))


def test_static_bundle_is_committed():
    assert (STATIC / "index.html").exists(), (
        f"{STATIC}/index.html manquant : lancez ./build.sh à la racine du dépôt et commitez static/."
    )
    assert any(STATIC.glob("assets/*.js")), "aucun bundle JavaScript dans static/assets/"


def test_index_references_existing_assets():
    """Un index.html d'un build et des assets d'un autre donneraient une page blanche."""
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    referenced = [part.split('"')[0] for part in index.split('/assets/')[1:]]
    assert referenced, "index.html ne référence aucun asset"
    for name in referenced:
        assert (STATIC / "assets" / name).exists(), f"index.html référence assets/{name}, absent du bundle"


def test_bundle_contains_recent_features():
    text = _bundle_text()
    missing = [feature for feature, marker in RECENT_UI_MARKERS.items() if marker not in text]
    assert not missing, (
        f"static/ ne contient pas : {', '.join(missing)}. "
        "Le frontend a changé sans être recompilé — lancez ./build.sh puis commitez static/."
    )


def test_package_version_matches_backend():
    """Les deux paquets sont distribués ensemble : ils portent la même version."""
    backend_pyproject = Path(__file__).resolve().parents[2] / "backend" / "pyproject.toml"
    if not backend_pyproject.exists():
        return  # installé depuis un wheel, sans le dépôt : rien à comparer
    for line in backend_pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            assert line.split('"')[1] == __version__
            return
    raise AssertionError("version introuvable dans backend/pyproject.toml")
