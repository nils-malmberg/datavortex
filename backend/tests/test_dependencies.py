"""Phase 10.3 : les dépendances déclarées sont des intervalles, pas des versions figées.

Un `==` empêche l'installation dès qu'un miroir d'entreprise n'a pas ce
wheel précis ; une borne haute absente laisse passer la prochaine version
majeure, non testée. Ces tests lisent les deux pyproject.toml distribués.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECTS = [ROOT / "backend" / "pyproject.toml", ROOT / "datavortex-cli" / "pyproject.toml"]

# Une ligne de dépendance :  "nom[extra]>=1.2,<2.0; marker",
_DEP_LINE = re.compile(r'^\s*"(?P<name>[A-Za-z0-9_.-]+)(?:\[[^\]]*\])?(?P<spec>[^";]*)(?:;[^"]*)?",\s*(?:#.*)?$')


def _dependency_lines(pyproject: Path) -> list[tuple[str, str]]:
    """Entrées des tableaux `dependencies = [...]` et des extras (`dev = [...]`)."""
    found, in_array = [], False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if re.match(r"^(dependencies|[a-z_]+) = \[\s*$", line) and not line.startswith("required-environments"):
            in_array = True
            continue
        if in_array and line.startswith("]"):
            in_array = False
            continue
        match = _DEP_LINE.match(line) if in_array else None
        if match and not line.lstrip().startswith("#"):
            found.append((match.group("name"), match.group("spec").strip()))
    return found


@pytest.mark.parametrize("pyproject", PYPROJECTS, ids=lambda p: p.parent.name)
def test_dependencies_are_ranges_not_pins(pyproject):
    deps = _dependency_lines(pyproject)
    assert deps, f"aucune dépendance trouvée dans {pyproject}"
    pinned = [f"{name}{spec}" for name, spec in deps if "==" in spec]
    assert not pinned, f"versions figées dans {pyproject.name} : {pinned}"


@pytest.mark.parametrize("pyproject", PYPROJECTS, ids=lambda p: p.parent.name)
def test_dependencies_have_both_bounds(pyproject):
    unbounded = [
        f"{name}{spec or ' (aucune contrainte)'}"
        for name, spec in _dependency_lines(pyproject)
        if ">=" not in spec or "<" not in spec.replace("<=", "")
    ]
    assert not unbounded, f"dépendances sans plancher ou sans plafond dans {pyproject.name} : {unbounded}"


def test_python_window_is_shared_by_backend_and_cli():
    """Le CLI installe le backend : ils doivent accepter les mêmes interpréteurs."""
    windows = []
    for pyproject in PYPROJECTS:
        match = re.search(r'^requires-python = "([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        assert match, f"requires-python absent de {pyproject}"
        windows.append(match.group(1))
    assert windows[0] == windows[1], windows
