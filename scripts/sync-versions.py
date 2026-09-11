#!/usr/bin/env python3
"""Aligne tous les numéros de version du dépôt sur une seule valeur.

    python scripts/sync-versions.py            # vérifie que tout est cohérent
    python scripts/sync-versions.py 1.2.1      # aligne tout sur 1.2.1

Six fichiers portent un numéro de version, et ils avaient divergé (backend
1.0.4, frontend 1.0.3, CLI 1.0.4…). Sans argument, le script ne modifie rien
et sort en erreur si les fichiers ne s'accordent pas : c'est ce que la CI
exécute, pour qu'une divergence ne puisse plus passer inaperçue.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (fichier, motif) — le groupe 1 capture le numéro. Un fichier peut porter la
# version à plusieurs endroits (package-lock.json) : toutes les occurrences
# du motif sont alignées.
TARGETS: list[tuple[str, str]] = [
    ("backend/pyproject.toml", r'^version = "([^"]+)"'),
    ("backend/app/main.py", r'^__version__ = "([^"]+)"'),
    ("frontend/package.json", r'^  "version": "([^"]+)"'),
    # Seules les deux entrées racine du lockfile décrivent ce paquet ; les
    # centaines d'autres "version" sont celles des dépendances.
    ("frontend/package-lock.json", r'"name": "datavortex-frontend",\n\s+"version": "([^"]+)"'),
    ("datavortex-cli/pyproject.toml", r'^version = "([^"]+)"'),
    ("datavortex-cli/datavortex/__init__.py", r'^__version__ = "([^"]+)"'),
    ("README.md", r'^\*\*v([^ ]+) — '),
    # Les lockfiles uv enregistrent la version du projet lui-même. `uv sync` les
    # réécrirait au prochain passage ; les aligner ici évite un lockfile qui
    # diverge du pyproject dans le même commit.
    ("backend/uv.lock", r'name = "datavortex-backend"\nversion = "([^"]+)"'),
    ("datavortex-cli/uv.lock", r'name = "datavortex(?:-backend)?"\nversion = "([^"]+)"'),
]

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def found_versions() -> dict[str, list[str]]:
    versions: dict[str, list[str]] = {}
    for path, pattern in TARGETS:
        versions[path] = re.findall(pattern, _read(path), flags=re.MULTILINE)
    return versions


def check() -> int:
    versions = found_versions()
    distinct = {v for found in versions.values() for v in found}
    for path, found in versions.items():
        marker = "✅" if len(distinct) == 1 and found else "❌"
        print(f"{marker} {path}: {', '.join(found) or 'aucune version trouvée'}")
    if not distinct or any(not found for found in versions.values()):
        print("\n❌ Au moins un fichier ne porte pas de version reconnaissable.")
        return 1
    if len(distinct) > 1:
        print(f"\n❌ Versions divergentes : {', '.join(sorted(distinct))}. "
              "Lancez `python scripts/sync-versions.py <version>` pour les aligner.")
        return 1
    print(f"\n✅ Toutes les versions sont à {distinct.pop()}")
    return 0


def sync(version: str) -> int:
    if not SEMVER.match(version):
        print(f"❌ '{version}' n'est pas une version MAJEUR.MINEUR.CORRECTIF")
        return 1
    for path, pattern in TARGETS:
        content = _read(path)
        # Ne remplace que le groupe capturé, pour ne toucher ni les guillemets
        # ni le reste de la ligne.
        updated, count = re.subn(
            pattern,
            lambda m: m.group(0)[: m.start(1) - m.start(0)] + version + m.group(0)[m.end(1) - m.start(0):],
            content,
            flags=re.MULTILINE,
        )
        if count == 0:
            print(f"❌ {path}: motif introuvable, fichier non modifié")
            return 1
        (ROOT / path).write_text(updated, encoding="utf-8")
        print(f"✅ {path} → {version} ({count} occurrence{'s' if count > 1 else ''})")
    print(f"\n✅ Toutes les versions alignées sur {version}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(sync(sys.argv[1]) if len(sys.argv) == 2 else check())
