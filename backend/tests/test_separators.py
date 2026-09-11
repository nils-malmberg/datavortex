"""Phase 10.2 : séparateurs prédéfinis, littéraux et par expression régulière."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data_engine import load_csv, regex_separator, validate_regex_separator
from app.main import app

client = TestClient(app)


def _parse(content: bytes, separator: str, separator_type: str = "preset"):
    resp = client.post("/api/upload", files={"file": ("data.csv", content, "text/csv")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    return client.post(
        "/api/parse",
        json={"session_id": session_id, "separator": separator, "separator_type": separator_type},
    )


# --- Séparateurs prédéfinis ------------------------------------------------


@pytest.mark.parametrize("sep", [",", ";", "\t", "|"])
def test_separator_preset(sep):
    content = f"name{sep}age{sep}score\nAlice{sep}30{sep}85.5\nBob{sep}25{sep}90\n".encode()
    resp = _parse(content, sep)
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["name", "age", "score"]
    assert body["n_rows"] == 2
    assert body["separator_type"] == "preset"


def test_separator_type_defaults_to_preset():
    resp = client.post("/api/upload", files={"file": ("d.csv", b"a,b\n1,2\n", "text/csv")})
    session_id = resp.json()["session_id"]
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    assert resp.json()["separator_type"] == "preset"


# --- Séparateurs regex -----------------------------------------------------


def test_separator_regex_multiple_spaces():
    """Le cas d'usage principal : colonnes alignées à coups d'espaces."""
    content = b"name     age   score\nAlice    30    85.5\nBob      25    90\n"
    resp = _parse(content, r"\s+", "regex")
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["name", "age", "score"]
    assert body["n_rows"] == 2
    assert body["separator_type"] == "regex"
    assert body["separator"] == r"\s+"


def test_separator_regex_comma_or_semicolon():
    content = b"name,age;score\nAlice;30,85.5\nBob,25;90\n"
    resp = _parse(content, r"[,;]", "regex")
    assert resp.status_code == 200
    assert resp.json()["columns"] == ["name", "age", "score"]
    assert resp.json()["n_rows"] == 2


def test_separator_regex_comma_with_surrounding_spaces():
    content = b"name , age ,score\nAlice ,30 , 85.5\n"
    resp = _parse(content, r"\s*,\s*", "regex")
    assert resp.status_code == 200
    assert resp.json()["columns"] == ["name", "age", "score"]


def test_separator_regex_single_metacharacter_is_treated_as_regex():
    """`\\|` doit rester une regex même s'il ne fait qu'un caractère utile."""
    resp = _parse(b"a|b\n1|2\n", r"\|", "regex")
    assert resp.status_code == 200
    assert resp.json()["columns"] == ["a", "b"]


def test_separator_regex_always_uses_python_engine():
    """Polars et le moteur C n'acceptent qu'un séparateur d'un caractère."""
    resp = _parse(b"a   b\n1   2\n", r"\s+", "regex")
    assert resp.json()["metrics"]["engine"] == "pandas-python"


def test_separator_regex_values_are_typed():
    resp = _parse(b"name  age\nAlice  30\nBob  25\n", r"\s+", "regex")
    assert resp.json()["column_types"] == {"name": "string", "age": "integer"}


# --- Validation ------------------------------------------------------------


@pytest.mark.parametrize("pattern", ["[", "(", "*", "\\"])  # le dernier : backslash final seul
def test_separator_validation_rejects_invalid_regex(pattern):
    resp = _parse(b"a,b\n1,2\n", pattern, "regex")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_SEPARATOR_REGEX"


@pytest.mark.parametrize("pattern", ["", "x*", r"\s*", "a?"])
def test_separator_validation_rejects_empty_matching_regex(pattern):
    """Un motif qui accepte la chaîne vide découperait entre chaque caractère."""
    resp = _parse(b"a,b\n1,2\n", pattern, "regex")
    assert resp.status_code == 400
    error = resp.json()["error"]
    assert error["code"] in ("INVALID_SEPARATOR_REGEX", "MISSING_SEPARATOR")


def test_separator_validation_unknown_type_rejected():
    resp = _parse(b"a,b\n1,2\n", ",", "auto")
    assert resp.status_code == 422


def test_separator_regex_producing_one_column_flagged():
    resp = _parse(b"a,b\n1,2\n", r"\t+", "regex")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SEPARATOR_LIKELY_WRONG"


def test_validate_regex_separator_helper():
    validate_regex_separator(r"\s+")
    with pytest.raises(ValueError, match="invalide"):
        validate_regex_separator("[")
    with pytest.raises(ValueError, match="vide"):
        validate_regex_separator("a*")


def test_regex_separator_wraps_single_characters():
    assert regex_separator("|") == "(?:|)"
    assert regex_separator(r"\|") == r"\|"
    assert regex_separator("[,;]") == "[,;]"


def test_load_csv_regex_skips_fast_engines(monkeypatch):
    """Même au-delà du seuil Polars, un motif passe par le moteur Python."""
    import app.data_engine as engine

    monkeypatch.setattr(engine, "POLARS_THRESHOLD_BYTES", 0)
    df, used = load_csv(b"a   b\n1   2\n", "utf-8", r"\s+", regex=True)
    assert used == "pandas-python"
    assert list(df.columns) == ["a", "b"]
