"""Phase 10 : formats compressés (CSV.GZ/BZ2/ZIP, Parquet toutes compressions, Feather)."""
from __future__ import annotations

import bz2
import gzip
import io
import zipfile

import polars as pl
import pytest
from fastapi.testclient import TestClient

from app.data_service import (
    MAX_DECOMPRESSED_BYTES,
    base_kind,
    compression_label,
    decompress_csv,
    detect_format,
    get_file_info,
)
from app.main import app

client = TestClient(app)

CSV_CONTENT = b"name,age,score\nAlice,30,85.5\nBob,25,90.0\nCharlie,35,78.2\n"


def _parquet_bytes(compression: str) -> bytes:
    df = pl.DataFrame({"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35], "score": [85.5, 90.0, 78.2]})
    buf = io.BytesIO()
    df.write_parquet(buf, compression=compression)
    return buf.getvalue()


def _feather_bytes() -> bytes:
    df = pl.DataFrame({"name": ["Alice", "Bob", "Charlie"], "age": [30, 25, 35], "score": [85.5, 90.0, 78.2]})
    buf = io.BytesIO()
    df.write_ipc(buf)
    return buf.getvalue()


def _zip_bytes(inner_name: str = "test.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(inner_name, CSV_CONTENT)
    return buf.getvalue()


# --- detect_format --------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("data.csv", "csv"),
        ("data.CSV", "csv"),
        ("data.tsv", "csv"),
        ("data.txt", "csv"),
        ("data.csv.gz", "csv_gz"),
        ("data.csv.bz2", "csv_bz2"),
        ("data.csv.zip", "csv_zip"),
        ("data.parquet", "parquet"),
        ("data.parquet.gz", "parquet_gz"),
        ("data.parquet.snappy", "parquet_snappy"),
        ("data.parquet.zstd", "parquet_zstd"),
        ("data.feather", "feather"),
        ("data.xlsx", "excel"),
        ("data.xls", "excel"),
        ("data.json", "json"),
    ],
)
def test_detect_format(filename, expected):
    assert detect_format(filename) == expected


def test_detect_format_compound_extension_priority():
    # '.csv.gz' doit être reconnu comme tel, pas retomber sur un suffixe '.gz' générique.
    assert detect_format("export.csv.gz") == "csv_gz"


def test_detect_format_unsupported_raises():
    with pytest.raises(ValueError):
        detect_format("data.exe")


def test_base_kind_collapses_compressed_variants():
    assert base_kind("csv") == base_kind("csv_gz") == base_kind("csv_bz2") == base_kind("csv_zip") == "csv"
    assert base_kind("parquet") == base_kind("parquet_gz") == base_kind("parquet_snappy") == base_kind("parquet_zstd") == "parquet"
    assert base_kind("feather") == "feather"


def test_compression_label():
    assert compression_label("csv_gz") == "gzip"
    assert compression_label("csv_bz2") == "bzip2"
    assert compression_label("csv_zip") == "zip"
    assert compression_label("parquet_zstd") == "zstd"
    assert compression_label("csv") == "none"


def test_get_file_info_estimates_uncompressed_size():
    info = get_file_info("big.csv.gz", 1_000_000, "csv_gz")
    assert info["format"] == "csv_gz"
    assert info["compression"] == "gzip"
    assert "estimated_uncompressed_mb" in info
    assert info["estimated_uncompressed_mb"] > info["size_mb"]


def test_get_file_info_no_estimate_for_plain_csv():
    info = get_file_info("plain.csv", 1_000_000, "csv")
    assert "estimated_uncompressed_mb" not in info


# --- decompress_csv --------------------------------------------------------


def test_decompress_csv_gz_roundtrip():
    assert decompress_csv(gzip.compress(CSV_CONTENT), "csv_gz") == CSV_CONTENT


def test_decompress_csv_bz2_roundtrip():
    assert decompress_csv(bz2.compress(CSV_CONTENT), "csv_bz2") == CSV_CONTENT


def test_decompress_csv_zip_roundtrip():
    assert decompress_csv(_zip_bytes(), "csv_zip") == CSV_CONTENT


def test_decompress_csv_zip_picks_first_csv_entry():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("readme.md", b"not a csv")
        archive.writestr("data.csv", CSV_CONTENT)
    assert decompress_csv(buf.getvalue(), "csv_zip") == CSV_CONTENT


def test_decompress_csv_zip_without_csv_entry_raises():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("readme.md", b"no csv here")
    with pytest.raises(ValueError):
        decompress_csv(buf.getvalue(), "csv_zip")


def test_decompress_csv_plain_is_noop():
    assert decompress_csv(CSV_CONTENT, "csv") is CSV_CONTENT


def test_decompress_gzip_bomb_rejected():
    huge = b"a" * (MAX_DECOMPRESSED_BYTES + 1024)
    gz = gzip.compress(huge, compresslevel=1)
    with pytest.raises(ValueError, match="dépasse la limite"):
        decompress_csv(gz, "csv_gz")


def test_decompress_zip_bomb_rejected_from_declared_size():
    # zipfile connaît la taille décompressée déclarée sans lire le contenu :
    # le rejet doit intervenir avant toute décompression réelle.
    huge = b"a" * (MAX_DECOMPRESSED_BYTES + 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bomb.csv", huge)
    with pytest.raises(ValueError, match="dépasse la limite"):
        decompress_csv(buf.getvalue(), "csv_zip")


# --- End-to-end upload/parse routes ----------------------------------------


def test_upload_csv_gz_end_to_end():
    resp = client.post("/api/upload", files={"file": ("data.csv.gz", gzip.compress(CSV_CONTENT), "application/gzip")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "csv_gz"
    assert body["file_kind"] == "csv"
    assert body["already_parsed"] is False
    assert body["detected_separator"] == ","

    resp = client.post("/api/parse", json={"session_id": body["session_id"], "separator": ","})
    assert resp.status_code == 200
    assert resp.json()["n_rows"] == 3


def test_upload_csv_bz2_end_to_end():
    resp = client.post("/api/upload", files={"file": ("data.csv.bz2", bz2.compress(CSV_CONTENT), "application/x-bzip2")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "csv_bz2"
    resp = client.post("/api/parse", json={"session_id": body["session_id"], "separator": ","})
    assert resp.status_code == 200
    assert resp.json()["n_rows"] == 3


def test_upload_csv_zip_end_to_end():
    resp = client.post("/api/upload", files={"file": ("data.csv.zip", _zip_bytes(), "application/zip")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "csv_zip"
    resp = client.post("/api/parse", json={"session_id": body["session_id"], "separator": ","})
    assert resp.status_code == 200
    assert resp.json()["n_rows"] == 3


@pytest.mark.parametrize("compression,ext", [("snappy", "parquet"), ("gzip", "parquet.gz"), ("zstd", "parquet.zstd")])
def test_upload_parquet_variants_already_parsed(compression, ext):
    resp = client.post(
        "/api/upload",
        files={"file": (f"data.{ext}", _parquet_bytes(compression), "application/octet-stream")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_kind"] == "parquet"
    assert body["already_parsed"] is True

    preview = client.get(f"/api/data/{body['session_id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["total_rows"] == 3
    assert preview.json()["columns"] == ["name", "age", "score"]


def test_upload_feather_already_parsed():
    resp = client.post("/api/upload", files={"file": ("data.feather", _feather_bytes(), "application/octet-stream")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["format"] == "feather"
    assert body["file_kind"] == "feather"
    assert body["already_parsed"] is True

    preview = client.get(f"/api/data/{body['session_id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["total_rows"] == 3


def test_upload_unsupported_format_rejected():
    resp = client.post("/api/upload", files={"file": ("data.exe", b"garbage", "application/octet-stream")})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_upload_csv_zip_without_csv_entry_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("readme.md", b"no csv here")
    resp = client.post("/api/upload", files={"file": ("data.csv.zip", buf.getvalue(), "application/zip")})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "DECOMPRESS_ERROR"


def test_upload_compressed_stats_and_groupby_work_downstream():
    """Le pipeline en aval (stats) ne doit voir aucune différence après décompression."""
    resp = client.post("/api/upload", files={"file": ("data.csv.gz", gzip.compress(CSV_CONTENT), "application/gzip")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})

    resp = client.get(f"/api/stats/{session_id}")
    assert resp.status_code == 200
    assert "age" in resp.json()["columns"]
