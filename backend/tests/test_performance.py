"""Tests du moteur de chargement rapide et de l'export en flux (Phase 9)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.data_engine import (
    POLARS_THRESHOLD_BYTES,
    is_utf8_compatible,
    load_csv,
    parse_csv_pandas_c,
    parse_csv_polars,
    should_use_fast_engine,
    sniff_sample,
)
from app.main import app
from app.parsing import parse_csv as parse_csv_pandas
from app.streaming import estimate_csv_bytes, iter_csv_chunks, validate_encoding

client = TestClient(app)

# Volontairement varié : entiers, flottants, texte, valeur manquante et un champ
# contenant le séparateur entre guillemets — c'est là que les moteurs divergent.
CSV = (
    b"name,age,score,city\n"
    b"Alice,30,85.5,Paris\n"
    b"Bob,25,90.0,Lyon\n"
    b'Charlie,35,,"Marseille, 13"\n'
    b"Diane,28,72.25,Lille\n"
)


def _upload_and_parse(content=CSV, filename="test.csv"):
    resp = client.post("/api/upload", files={"file": (filename, content, "text/csv")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    return session_id


# --- Sélection du moteur -------------------------------------------------------

def test_fast_engine_only_above_threshold():
    """Les petits fichiers gardent le chemin pandas historique."""
    assert not should_use_fast_engine(1024)
    assert not should_use_fast_engine(POLARS_THRESHOLD_BYTES - 1)
    assert should_use_fast_engine(POLARS_THRESHOLD_BYTES)


def test_load_csv_selects_engine_by_size_and_encoding():
    assert load_csv(CSV, "utf-8", ",")[1] == "pandas-python"
    assert load_csv(CSV, "utf-8", ",", size_bytes=10**9)[1] == "polars"
    # Polars ne lit que l'UTF-8 : un encoding exotique redescend sur le moteur C.
    assert load_csv(CSV, "latin-1", ",", size_bytes=10**9)[1] == "pandas-c"


def test_utf8_compatibility_detection():
    assert is_utf8_compatible("utf-8")
    assert is_utf8_compatible("UTF8")
    assert is_utf8_compatible("ascii")
    assert not is_utf8_compatible("latin-1")
    assert not is_utf8_compatible("")


def test_load_csv_reads_from_path(tmp_path):
    """Le chargement par chemin évite de matérialiser les octets en mémoire."""
    path = tmp_path / "data.csv"
    path.write_bytes(CSV)
    df, engine = load_csv(None, "utf-8", ",", path=path, size_bytes=10**9)
    assert engine == "polars"
    assert list(df.columns) == ["name", "age", "score", "city"]
    assert df.shape[0] == 4


# --- Équivalence entre moteurs -------------------------------------------------

@pytest.mark.parametrize(
    "content",
    [
        CSV,
        b"a,b\n1,2\n3,4\n",
        b"x,y\n1.5,hello\n,world\n",
        b"only_one_column\n1\n2\n",
    ],
    ids=["mixed", "ints", "nulls", "single-column"],
)
def test_engines_agree(content):
    """Les trois moteurs doivent produire le même tableau.

    C'est la garantie qui permet de basculer sur Polars au-delà du seuil sans
    changer ce que voit l'utilisateur.
    """
    reference = parse_csv_pandas(content, "utf-8", ",")
    from_polars = parse_csv_polars(content, ",")
    from_c = parse_csv_pandas_c(content, "utf-8", ",")

    assert list(from_polars.columns) == list(reference.columns)
    assert list(from_c.columns) == list(reference.columns)
    assert from_polars.shape == reference.shape
    assert from_c.shape == reference.shape

    # Comparaison sur le texte : les moteurs peuvent choisir int64 vs float64
    # pour une colonne, sans que les valeurs diffèrent.
    for col in reference.columns:
        assert from_polars[col].astype(str).tolist() == reference[col].astype(str).tolist()
        assert from_c[col].astype(str).tolist() == reference[col].astype(str).tolist()


def test_polars_preserves_quoted_separator():
    """Un séparateur entre guillemets ne doit pas couper le champ."""
    df = parse_csv_polars(CSV, ",")
    assert df.loc[2, "city"] == "Marseille, 13"


# --- Échantillonnage de détection ----------------------------------------------

def test_sniff_sample_is_bounded_and_cut_on_a_line_break():
    big = b"col_a,col_b\n" + b"1,2\n" * 200_000
    sample = sniff_sample(big)
    assert len(sample) < len(big)
    # La coupe se fait sur une fin de ligne : le dernier octet clôt un enregistrement.
    assert sample.endswith(b"2")
    assert sample.startswith(b"col_a,col_b\n")


def test_sniff_sample_returns_small_input_untouched():
    assert sniff_sample(CSV) == CSV


def test_separator_detected_on_large_file():
    """La détection sur échantillon reste correcte sur un fichier volumineux."""
    big = b"a;b;c\n" + b"1;2;3\n" * 50_000
    resp = client.post("/api/upload", files={"file": ("big.csv", big, "text/csv")})
    assert resp.status_code == 200
    assert resp.json()["detected_separator"] == ";"


# --- Export en flux ------------------------------------------------------------

def test_stream_writes_header_once():
    df = pd.DataFrame({"a": range(25), "b": ["x"] * 25})
    text = b"".join(iter_csv_chunks(df, chunk_rows=10)).decode()
    assert text.count("a,b") == 1
    assert len(text.strip().splitlines()) == 26  # 1 en-tête + 25 lignes


def test_stream_empty_dataframe_still_has_header():
    df = pd.DataFrame({"a": [], "b": []})
    assert b"".join(iter_csv_chunks(df)).decode().strip() == "a,b"


def test_stream_respects_separator_and_comment():
    df = pd.DataFrame({"a": [1], "b": [2]})
    text = b"".join(iter_csv_chunks(df, separator=";", header_comment="Filtre : x > 1")).decode()
    assert text.startswith("# Filtre : x > 1\n")
    assert "a;b" in text


def test_stream_chunking_matches_single_pass_output():
    """Le découpage ne doit rien changer au contenu produit."""
    df = pd.DataFrame({"a": range(100), "b": [f"v{i}" for i in range(100)]})
    chunked = b"".join(iter_csv_chunks(df, chunk_rows=7)).decode()
    assert chunked == df.to_csv(index=False)


def test_stream_invalid_chunk_size_falls_back():
    df = pd.DataFrame({"a": range(5)})
    assert b"".join(iter_csv_chunks(df, chunk_rows=0)).decode() == df.to_csv(index=False)


def test_validate_encoding():
    validate_encoding("utf-8")
    with pytest.raises(LookupError):
        validate_encoding("pas-un-encoding")


def test_estimate_csv_bytes():
    df = pd.DataFrame({"a": range(1000)})
    estimate = estimate_csv_bytes(df)
    actual = len(df.to_csv(index=False).encode())
    assert estimate == pytest.approx(actual, rel=0.2)
    assert estimate_csv_bytes(df.head(0)) is None


# --- Routes d'export en flux ---------------------------------------------------

def test_export_stream_route_returns_full_csv():
    session_id = _upload_and_parse()
    resp = client.post("/api/export/csv/stream", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    assert "Alice" in resp.text and "Diane" in resp.text


def test_export_stream_matches_non_streaming_export():
    """Les deux exports doivent produire exactement le même fichier."""
    session_id = _upload_and_parse()
    body = {"session_id": session_id, "separator": ";", "include_filter_comment": False}
    streamed = client.post("/api/export/csv/stream", json=body).text
    buffered = client.post("/api/export/csv", json={**body, "encoding": "utf-8"}).text
    assert streamed == buffered


def test_export_stream_includes_filter_comment():
    session_id = _upload_and_parse()
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "age", "operator": "gt", "value": 26}},
    )
    resp = client.post("/api/export/csv/stream", json={"session_id": session_id})
    assert resp.text.startswith("# Filtre appliqué")
    assert "Bob" not in resp.text  # 25 ans, écarté par le filtre


def test_export_stream_rejects_bad_encoding_before_streaming():
    """L'erreur doit être un vrai 400, pas un fichier tronqué."""
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/export/csv/stream",
        json={"session_id": session_id, "encoding": "pas-un-encoding"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ENCODING"


def test_export_stream_unknown_session():
    resp = client.post("/api/export/csv/stream", json={"session_id": "inconnu"})
    assert resp.status_code == 404


def test_export_estimate_route():
    session_id = _upload_and_parse()
    resp = client.get(f"/api/export/csv/estimate/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows"] == 4
    assert body["columns"] == 4
    assert body["estimated_bytes"] > 0


# --- Parsing : métriques et grand fichier -------------------------------------

def test_parse_reports_engine_metrics():
    session_id = _upload_and_parse()
    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    metrics = resp.json()["metrics"]
    assert metrics["engine"] == "pandas-python"
    assert metrics["duration_seconds"] >= 0
    assert metrics["rows_processed"] == 4


def test_large_upload_spills_to_disk_and_parses():
    """Au-delà du seuil, la source part sur disque et l'analyse passe par Polars."""
    from app.session_store import SPILL_THRESHOLD_BYTES, store

    row = b"1,2.5,texte_de_remplissage_pour_atteindre_le_seuil\n"
    n_rows = (SPILL_THRESHOLD_BYTES // len(row)) + 1000
    content = b"a,b,c\n" + row * n_rows
    assert len(content) > SPILL_THRESHOLD_BYTES

    resp = client.post("/api/upload", files={"file": ("gros.csv", content, "text/csv")})
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]

    session = store.get(session_id)
    assert session.source_path() is not None, "le fichier aurait dû être déversé sur disque"
    assert session.raw_bytes == b"", "les octets auraient dû être relâchés"

    resp = client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_rows"] == n_rows
    assert body["metrics"]["engine"] == "polars"

    # La fermeture de session doit nettoyer le fichier temporaire.
    spill_path = session.source_path()
    client.delete(f"/api/session/{session_id}")
    import os

    assert not os.path.exists(spill_path)


def test_polars_and_pandas_paths_give_same_rows_end_to_end():
    """Un même contenu, analysé par les deux chemins, donne le même aperçu."""
    row = b"1,2.5,abcdefghijklmnopqrstuvwxyz\n"
    content = b"a,b,c\n" + row * 2000
    small_df = parse_csv_pandas(content, "utf-8", ",")
    big_df, engine = load_csv(content, "utf-8", ",", size_bytes=10**9)
    assert engine == "polars"
    assert small_df.shape == big_df.shape
    assert small_df["c"].tolist() == big_df["c"].tolist()


def test_upload_rejects_oversized_file(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module, "MAX_UPLOAD_SIZE_BYTES", 100)
    resp = client.post("/api/upload", files={"file": ("x.csv", b"a,b\n" + b"1,2\n" * 100, "text/csv")})
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_health_reports_memory_and_engine_availability():
    body = client.get("/api/health").json()
    assert body["polars_available"] is True
    assert body["memory"]["rss_mb"] > 0
    assert "system_available_mb" in body["memory"]
