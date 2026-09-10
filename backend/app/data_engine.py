"""Moteur de chargement des données (Phase 9).

Le parsing est le poste de coût dominant sur un gros fichier : avant cette
phase, un CSV passait systématiquement par `pd.read_csv(engine="python")`,
l'analyseur le plus lent de pandas (boucle Python ligne à ligne). Ce module le
remplace par une cascade de trois moteurs, du plus rapide au plus permissif :

1. **Polars** — analyseur Rust multi-cœur, 10 à 50x plus rapide que l'analyseur
   Python et nettement plus économe en mémoire. Utilisable quand le texte est
   décodable en UTF-8 (cas de l'écrasante majorité des fichiers).
2. **pandas, moteur C** — repli rapide quand Polars échoue ou que l'encoding
   n'est pas compatible UTF-8. Exige un séparateur d'un seul caractère.
3. **pandas, moteur Python** — repli final, le plus tolérant aux fichiers mal
   formés. C'est le comportement historique, conservé intact.

Le choix n'est appliqué qu'au-delà d'un seuil de taille (`POLARS_THRESHOLD_BYTES`) :
en dessous, le gain se compte en millisecondes et ne justifie pas d'exposer les
petits fichiers à des différences d'inférence de type entre moteurs. C'est la
stratégie « dual support » décrite au §2.2 de la spec Phase 9.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from app.parsing import parse_csv as parse_csv_pandas

try:  # pragma: no cover - Polars est une dépendance dure, ce garde-fou est défensif
    import polars as pl

    POLARS_AVAILABLE = True
except ImportError:  # pragma: no cover
    pl = None
    POLARS_AVAILABLE = False

# Au-delà de cette taille, on bascule sur le moteur rapide (§2.2 de la spec).
# Réglable sans modifier le code : le seuil de 50MB est prudent, et un fichier
# de 30MB — 500 000 lignes environ — reste analysé par le moteur Python, dix
# fois plus lentement. DATAVORTEX_FAST_PARSE_MB permet d'abaisser ce seuil.
POLARS_THRESHOLD_BYTES = int(float(os.environ.get("DATAVORTEX_FAST_PARSE_MB", "50")) * 1024 * 1024)

# Encodings que Polars sait lire sans transcodage préalable.
UTF8_ALIASES = {"utf-8", "utf8", "ascii", "us-ascii", "utf-8-sig", "utf8-sig"}

# Taille d'échantillon suffisante pour détecter encoding et séparateur. Analyser
# 500MB pour trancher entre « , » et « ; » est un gaspillage pur : les premières
# lignes portent la même information.
SNIFF_SAMPLE_BYTES = 256 * 1024

Source = Union[bytes, str, Path]


def is_utf8_compatible(encoding: str) -> bool:
    return (encoding or "").lower().replace("_", "-") in UTF8_ALIASES


def should_use_fast_engine(size_bytes: int) -> bool:
    """Le moteur rapide n'est enclenché qu'au-delà du seuil de taille."""
    return size_bytes >= POLARS_THRESHOLD_BYTES


def _to_polars_input(source: Source):
    """Polars lit soit un chemin (aucune copie en RAM), soit un tampon."""
    if isinstance(source, (str, Path)):
        return str(source)
    return io.BytesIO(source)


def parse_csv_polars(source: Source, separator: str, encoding: str = "utf-8") -> pd.DataFrame:
    """Analyse un CSV avec Polars et renvoie un DataFrame pandas.

    Le reste de l'application (stats, plotting, ML, rapports) travaille sur
    pandas ; Polars sert ici de moteur d'analyse, pas de représentation. La
    conversion passe par Arrow, sans recopie pour les colonnes numériques.
    """
    if not POLARS_AVAILABLE:  # pragma: no cover
        raise RuntimeError("Polars n'est pas installé.")

    frame = pl.read_csv(
        _to_polars_input(source),
        separator=separator,
        # Polars n'accepte que `utf8` et `utf8-lossy` ; l'appelant (`load_csv`)
        # ne route ici que des encodings compatibles UTF-8. `utf8-lossy` remplace
        # les octets invalides plutôt que d'échouer, reproduisant le
        # `errors="replace"` du chemin pandas historique.
        encoding="utf8-lossy",
        # Équivalents Polars du `on_bad_lines="skip"` / `skip_blank_lines` pandas.
        truncate_ragged_lines=True,
        ignore_errors=True,
        # L'inférence par défaut ne regarde que 100 lignes, ce qui classe en
        # entier une colonne dont les décimales n'arrivent que plus bas.
        infer_schema_length=10_000,
    )
    return frame.to_pandas()


def parse_csv_pandas_c(raw_bytes: bytes, encoding: str, separator: str) -> pd.DataFrame:
    """Repli rapide : moteur C de pandas (exige un séparateur d'un caractère)."""
    if len(separator) != 1:
        raise ValueError("Le moteur C exige un séparateur d'un seul caractère.")
    text = raw_bytes.decode(encoding, errors="replace")
    return pd.read_csv(
        io.StringIO(text),
        sep=separator,
        engine="c",
        on_bad_lines="skip",
        skip_blank_lines=True,
    )


def load_csv(
    raw_bytes: Optional[bytes],
    encoding: str,
    separator: str,
    *,
    path: Optional[Union[str, Path]] = None,
    size_bytes: Optional[int] = None,
) -> tuple[pd.DataFrame, str]:
    """Charge un CSV via le moteur le plus rapide qui aboutisse.

    `path` (fichier déversé sur disque) est préféré à `raw_bytes` quand il est
    disponible : Polars lit alors le fichier sans jamais matérialiser son
    contenu en mémoire Python.

    Renvoie le DataFrame et le nom du moteur effectivement utilisé, que les
    routes remontent dans leurs métriques.
    """
    if size_bytes is None:
        if path is not None:
            size_bytes = Path(path).stat().st_size
        else:
            size_bytes = len(raw_bytes or b"")

    if should_use_fast_engine(size_bytes):
        source: Optional[Source] = path if path is not None else raw_bytes
        if POLARS_AVAILABLE and source is not None and is_utf8_compatible(encoding):
            try:
                return parse_csv_polars(source, separator, encoding), "polars"
            except Exception:
                # Polars est plus strict que pandas sur les fichiers biscornus :
                # on redescend d'un cran plutôt que de faire échouer l'upload.
                pass

        if raw_bytes is None and path is not None:
            raw_bytes = Path(path).read_bytes()

        if raw_bytes is not None:
            try:
                return parse_csv_pandas_c(raw_bytes, encoding, separator), "pandas-c"
            except Exception:
                pass

    if raw_bytes is None and path is not None:
        raw_bytes = Path(path).read_bytes()

    return parse_csv_pandas(raw_bytes or b"", encoding, separator), "pandas-python"


def sniff_sample(raw_bytes: bytes) -> bytes:
    """Échantillon de tête utilisé pour deviner encoding et séparateur.

    Coupé sur une frontière de ligne pour ne pas tronquer un caractère
    multi-octets au milieu, ce qui fausserait la détection d'encoding.
    """
    if len(raw_bytes) <= SNIFF_SAMPLE_BYTES:
        return raw_bytes
    sample = raw_bytes[:SNIFF_SAMPLE_BYTES]
    cut = sample.rfind(b"\n")
    return sample[:cut] if cut > 0 else sample
