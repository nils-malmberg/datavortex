"""Détection et chargement des formats compressés (Phase 10).

Le reste de l'application ne connaît que quatre natures de contenu : CSV,
Excel, JSON, et désormais les formats colonnaires (Parquet/Feather). Ce module
absorbe la diversité des emballages compressés dans ces quatre natures, pour
que `main.py` et `session_store.py` n'aient jamais à distinguer un
`.csv.gz` d'un `.csv` une fois le fichier reçu :

- **CSV compressé** (`.csv.gz`, `.csv.bz2`, `.csv.zip`) est ramené à des octets
  CSV en clair dès l'upload, puis suit exactement le chemin d'un `.csv` normal
  (détection encoding/séparateur, cascade Polars/pandas, spill sur disque).
  `.csv.gz` n'a en réalité pas besoin d'être décompressé ici : Polars détecte
  et décompresse le gzip lui-même à la volée (confirmé empiriquement — magic
  bytes, indépendamment de l'extension). On le décompresse quand même en amont
  par cohérence : cela évite qu'un repli pandas (qui, lui, ne décompresse pas)
  ne reçoive des octets gzip bruts si Polars échoue pour une autre raison.
- **Parquet/Feather**, quelle que soit leur codec de compression interne
  (snappy/gzip/zstd — transparente pour le lecteur), sont chargés une seule
  fois à l'upload, comme Excel/JSON, puisqu'il n'y a pas de séparateur à
  ajuster après coup.

Une bombe de décompression (fichier compressé minuscule, contenu décompressé
énorme) est un vecteur de déni de service classique sur ce genre de endpoint :
`decompress_csv` borne donc la taille décompressée plutôt que de faire
confiance à la taille annoncée par l'archive.
"""
from __future__ import annotations

import bz2
import gzip
import io
import os
import zipfile

import pandas as pd

try:  # pragma: no cover - cohérent avec la garde de data_engine.py
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:  # pragma: no cover
    pl = None
    POLARS_AVAILABLE = False

# Extensions composées vérifiées avant leur suffixe simple ('.csv.gz' avant
# '.gz', qui n'est d'ailleurs même pas listé seul : un '.gz' sans '.csv' ou
# '.parquet' devant n'a pas de sens applicatif ici et reste rejeté.
_COMPOUND_EXTENSIONS: list[tuple[str, str]] = [
    (".csv.gz", "csv_gz"),
    (".csv.bz2", "csv_bz2"),
    (".csv.zip", "csv_zip"),
    (".parquet.gz", "parquet_gz"),
    (".parquet.snappy", "parquet_snappy"),
    (".parquet.zstd", "parquet_zstd"),
    (".xlsx", "excel"),
    (".xls", "excel"),
    (".json", "json"),
    (".parquet", "parquet"),
    (".feather", "feather"),
    (".csv", "csv"),
    (".tsv", "csv"),
    (".txt", "csv"),
]

# Nature réelle du contenu une fois l'emballage retiré : c'est cette valeur que
# `session.file_kind` porte, et sur laquelle tout le reste de l'application
# (spill, cascade CSV, export, rapport) continue de brancher sa logique.
_BASE_KIND = {
    "csv": "csv",
    "csv_gz": "csv",
    "csv_bz2": "csv",
    "csv_zip": "csv",
    "parquet": "parquet",
    "parquet_gz": "parquet",
    "parquet_snappy": "parquet",
    "parquet_zstd": "parquet",
    "feather": "feather",
    "excel": "excel",
    "json": "json",
}

_COMPRESSION_LABELS = {
    "csv_gz": "gzip",
    "csv_bz2": "bzip2",
    "csv_zip": "zip",
    "parquet_gz": "gzip",
    "parquet_snappy": "snappy",
    "parquet_zstd": "zstd",
}

# Formats déjà entièrement chargés en DataFrame à l'upload (comme Excel/JSON) :
# pas de séparateur à confirmer, pas de deuxième passe de parsing.
COLUMNAR_KINDS = {"parquet", "feather"}

# Ceiling défensif contre les bombes de décompression : un fichier .csv.bz2 de
# quelques Mo ne doit jamais pouvoir gonfler à plusieurs dizaines de Go en
# mémoire serveur. Aligné par défaut sur MAX_UPLOAD_SIZE_BYTES (main.py) : la
# compression permet de transférer moins d'octets sur le réseau, pas de
# dépasser le budget mémoire pour lequel le reste du pipeline (stats, plotting,
# ML) est dimensionné. Réglable indépendamment via DATAVORTEX_MAX_DECOMPRESSED_MB
# si un déploiement veut explicitement autoriser un contenu décompressé plus
# large que la limite d'upload brute.
MAX_DECOMPRESSED_BYTES = int(float(os.environ.get("DATAVORTEX_MAX_DECOMPRESSED_MB", "500")) * 1024 * 1024)

_DECOMPRESS_CHUNK_BYTES = 4 * 1024 * 1024


def detect_format(filename: str) -> str:
    """Devine le format détaillé (ex: 'csv_gz') depuis le nom de fichier."""
    lower = (filename or "").lower()
    for ext, fmt in _COMPOUND_EXTENSIONS:
        if lower.endswith(ext):
            return fmt
    raise ValueError(f"Format de fichier non pris en charge : {filename}")


def base_kind(fmt: str) -> str:
    """Nature de contenu sous-jacente ('csv' pour tous les CSV compressés, etc)."""
    return _BASE_KIND[fmt]


def compression_label(fmt: str) -> str:
    return _COMPRESSION_LABELS.get(fmt, "none")


def get_file_info(filename: str, size_bytes: int, fmt: str) -> dict:
    """Métadonnées affichées à l'utilisateur juste après l'upload."""
    size_mb = round(size_bytes / 1024 / 1024, 2)
    info = {
        "filename": filename,
        "format": fmt,
        "size_mb": size_mb,
        "compression": compression_label(fmt),
    }
    if fmt in ("csv_gz", "csv_bz2"):
        # Ratio de compression typique d'un CSV textuel : 10 à 20%. Purement
        # indicatif — affiché avant que la taille réelle ne soit connue.
        info["estimated_uncompressed_mb"] = round(size_mb / 0.15, 2)
    return info


def _decompress_gzip_bounded(raw_bytes: bytes) -> bytes:
    chunks: list[bytes] = []
    total = 0
    with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes)) as handle:
        while True:
            chunk = handle.read(_DECOMPRESS_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DECOMPRESSED_BYTES:
                raise ValueError(
                    f"Le fichier décompressé dépasse la limite autorisée "
                    f"({MAX_DECOMPRESSED_BYTES // (1024 * 1024)}MB)."
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _decompress_bz2_bounded(raw_bytes: bytes) -> bytes:
    chunks: list[bytes] = []
    total = 0
    with bz2.BZ2File(io.BytesIO(raw_bytes)) as handle:
        while True:
            chunk = handle.read(_DECOMPRESS_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DECOMPRESSED_BYTES:
                raise ValueError(
                    f"Le fichier décompressé dépasse la limite autorisée "
                    f"({MAX_DECOMPRESSED_BYTES // (1024 * 1024)}MB)."
                )
            chunks.append(chunk)
    return b"".join(chunks)


def _decompress_zip_bounded(raw_bytes: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
        csv_names = [n for n in archive.namelist() if n.lower().endswith((".csv", ".tsv", ".txt"))]
        if not csv_names:
            raise ValueError("Aucun fichier CSV trouvé dans l'archive zip.")
        entry = archive.getinfo(csv_names[0])
        # `file_size` (taille déclarée dans l'archive) permet de rejeter une
        # bombe zip avant même de lire un octet décompressé.
        if entry.file_size > MAX_DECOMPRESSED_BYTES:
            raise ValueError(
                f"Le fichier décompressé dépasse la limite autorisée "
                f"({MAX_DECOMPRESSED_BYTES // (1024 * 1024)}MB)."
            )
        chunks: list[bytes] = []
        total = 0
        with archive.open(entry) as handle:
            while True:
                chunk = handle.read(_DECOMPRESS_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DECOMPRESSED_BYTES:
                    raise ValueError(
                        f"Le fichier décompressé dépasse la limite autorisée "
                        f"({MAX_DECOMPRESSED_BYTES // (1024 * 1024)}MB)."
                    )
                chunks.append(chunk)
        return b"".join(chunks)


def decompress_csv(raw_bytes: bytes, fmt: str) -> bytes:
    """Ramène un CSV compressé à des octets texte bruts.

    `fmt == 'csv'` est un no-op : c'est le cas le plus fréquent, traité en
    premier pour ne jamais copier les octets d'un gros fichier non compressé.
    """
    if fmt == "csv":
        return raw_bytes
    if fmt == "csv_gz":
        return _decompress_gzip_bounded(raw_bytes)
    if fmt == "csv_bz2":
        return _decompress_bz2_bounded(raw_bytes)
    if fmt == "csv_zip":
        return _decompress_zip_bounded(raw_bytes)
    raise ValueError(f"Format CSV inconnu : {fmt}")


def load_columnar(raw_bytes: bytes, fmt: str) -> pd.DataFrame:
    """Charge un Parquet (toute compression) ou Feather en DataFrame pandas."""
    if not POLARS_AVAILABLE:  # pragma: no cover
        raise RuntimeError("Polars est requis pour lire les fichiers Parquet/Feather.")

    buffer = io.BytesIO(raw_bytes)
    try:
        if fmt == "feather":
            frame = pl.read_ipc(buffer)
        else:
            # snappy/gzip/zstd sont des codecs internes au fichier Parquet,
            # transparents pour read_parquet — aucune branche par variante.
            frame = pl.read_parquet(buffer)
    except Exception as exc:
        raise ValueError(f"Impossible de lire le fichier {fmt} : {exc}")
    return frame.to_pandas()

