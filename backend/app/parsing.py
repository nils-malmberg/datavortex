"""Détection d'encoding/séparateur et parsing des fichiers en DataFrame."""
from __future__ import annotations

import csv
import io
import warnings

import chardet
import pandas as pd

CANDIDATE_SEPARATORS = [",", ";", "\t", "|"]

# Fenêtre de tête dans laquelle `detect_column_type` cherche ses 30 valeurs
# non nulles témoins. Assez large pour traverser un début de fichier clairsemé,
# assez étroite pour rester en temps constant sur un fichier de plusieurs
# millions de lignes.
TYPE_SAMPLE_WINDOW = 10_000
SEPARATOR_LABELS = {
    ",": "Virgule ( , )",
    ";": "Point-virgule ( ; )",
    "\t": "Tabulation ( \\t )",
    "|": "Pipe ( | )",
}


def detect_encoding(raw_bytes: bytes) -> str:
    """Détecte l'encoding d'un fichier via chardet, avec repli sur utf-8."""
    if not raw_bytes:
        return "utf-8"
    result = chardet.detect(raw_bytes)
    encoding = (result or {}).get("encoding") or "utf-8"
    confidence = (result or {}).get("confidence") or 0
    # chardet peut renvoyer des encodings exotiques peu fiables sur peu de données.
    if confidence < 0.5:
        encoding = "utf-8"
    try:
        raw_bytes.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        encoding = "utf-8"
    return encoding


def detect_separator(text: str) -> str:
    """Détecte le séparateur le plus probable parmi , ; \\t |.

    Stratégie : tente d'abord csv.Sniffer (robuste sur des CSV bien formés),
    puis retombe sur une heuristique de comptage/consistance par ligne.
    """
    sample = "\n".join(text.splitlines()[:20]) if text else ""
    if not sample.strip():
        return ","

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(CANDIDATE_SEPARATORS))
        if dialect.delimiter in CANDIDATE_SEPARATORS:
            return dialect.delimiter
    except csv.Error:
        pass

    lines = [line for line in sample.splitlines() if line.strip()]
    best_sep = ","
    best_score = (-1, -1)  # (consistance, nb_champs)
    for sep in CANDIDATE_SEPARATORS:
        counts = [line.count(sep) for line in lines]
        if not counts or max(counts) == 0:
            continue
        is_consistent = len(set(counts)) == 1
        score = (1 if is_consistent else 0, counts[0])
        if score > best_score:
            best_score = score
            best_sep = sep
    return best_sep


def parse_csv(raw_bytes: bytes, encoding: str, separator: str) -> pd.DataFrame:
    """Parse un CSV en DataFrame pandas avec gestion basique des erreurs."""
    text = raw_bytes.decode(encoding, errors="replace")
    buffer = io.StringIO(text)
    try:
        df = pd.read_csv(
            buffer,
            sep=separator,
            engine="python",
            on_bad_lines="skip",
            skip_blank_lines=True,
        )
    except Exception as exc:  # pragma: no cover - repli défensif
        raise ValueError(f"Impossible de parser le fichier avec le séparateur '{separator}' : {exc}")

    if df.shape[1] <= 1 and separator != ",":
        # Probablement un mauvais séparateur : on relève l'anomalie côté appelant.
        pass
    return df


def parse_excel(raw_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(raw_bytes))


def parse_json(raw_bytes: bytes, encoding: str) -> pd.DataFrame:
    text = raw_bytes.decode(encoding, errors="replace")
    return pd.read_json(io.StringIO(text))


def detect_column_type(series: pd.Series) -> str:
    """Détecte le type logique d'une colonne : integer, float, boolean, datetime, string."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    # Colonne "object" : on tente une détection de dates sur un échantillon.
    # L'échantillon est prélevé sur une fenêtre de tête bornée, pas sur la
    # colonne entière : `dropna().astype(str)` sur 3 millions de valeurs pour
    # n'en regarder que 30 coûtait ~100 ms par colonne, payés à chaque appel —
    # et cette fonction est appelée par presque toutes les routes.
    non_null = series.head(TYPE_SAMPLE_WINDOW).dropna()
    if len(non_null) == 0:
        # Fenêtre entièrement vide : la colonne peut malgré tout porter des
        # valeurs plus loin, on paie alors le parcours complet (cas rare).
        non_null = series.dropna()
    if len(non_null) == 0:
        return "string"

    sample = non_null.head(30).astype(str)
    try:
        # pandas avertit (« Could not infer format… ») dès qu'il ne devine pas
        # de format commun et retombe sur dateutil : c'est précisément ce
        # qu'on lui demande ici — tester si ça ressemble à des dates — et
        # cette fonction tourne sur chaque colonne texte à presque chaque
        # route. Le résultat est le même, sans inonder le terminal.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(sample, errors="coerce")
        success_ratio = parsed.notna().mean()
    except Exception:
        success_ratio = 0.0

    if success_ratio >= 0.8:
        return "datetime"
    return "string"


def detect_column_types(df: pd.DataFrame) -> dict[str, str]:
    return {col: detect_column_type(df[col]) for col in df.columns}
