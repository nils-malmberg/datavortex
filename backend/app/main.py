"""DataVortex - Backend FastAPI (Phase 1 MVP).

Fonctionnalités :
- Upload de fichiers (CSV / Excel / JSON) stockés en mémoire par session
- Détection automatique de l'encoding et du séparateur (pour les CSV)
- Parsing en DataFrame pandas avec le séparateur choisi/confirmé
- Aperçu des données (100 premières lignes)
- Statistiques descriptives par colonne
"""
from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.errors import (
    AppError,
    app_error_handler,
    column_not_found,
    not_parsed_yet,
    session_not_found,
    unhandled_exception_handler,
)
from app.models import ParseRequest, ParseResponse, UploadResponse
from app.parsing import (
    CANDIDATE_SEPARATORS,
    detect_column_types,
    detect_encoding,
    detect_file_kind,
    detect_separator,
    parse_csv,
    parse_excel,
    parse_json,
)
from app.serialize import dataframe_to_records
from app.session_store import Session, store
from app.stats import column_summary, dataframe_summary

MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
PREVIEW_ROWS = 100

app = FastAPI(title="DataVortex API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


def _get_session_or_404(session_id: str) -> Session:
    session = store.get(session_id)
    if session is None:
        raise session_not_found(session_id)
    return session


def _get_parsed_session_or_error(session_id: str) -> Session:
    session = _get_session_or_404(session_id)
    if session.df is None:
        raise not_parsed_yet(session_id)
    return session


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    raw_bytes = await file.read()

    if not raw_bytes:
        raise AppError(400, "EMPTY_FILE", "Le fichier envoyé est vide.")

    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise AppError(
            413,
            "FILE_TOO_LARGE",
            f"Le fichier dépasse la taille maximale autorisée ({MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB).",
        )

    filename = file.filename or "fichier_sans_nom"
    file_kind = detect_file_kind(filename)
    encoding = detect_encoding(raw_bytes) if file_kind != "excel" else "n/a"

    detected_separator = None
    raw_preview: list[str] = []
    already_parsed = False
    df = None

    if file_kind == "csv":
        text = raw_bytes.decode(encoding, errors="replace")
        detected_separator = detect_separator(text)
        raw_preview = text.splitlines()[:5]
    elif file_kind == "excel":
        try:
            df = parse_excel(raw_bytes)
        except Exception as exc:
            raise AppError(400, "PARSE_ERROR", f"Impossible de lire le fichier Excel : {exc}")
        already_parsed = True
    elif file_kind == "json":
        try:
            df = parse_json(raw_bytes, encoding)
        except Exception as exc:
            raise AppError(400, "PARSE_ERROR", f"Impossible de lire le fichier JSON : {exc}")
        already_parsed = True

    session = store.create(
        filename=filename,
        file_kind=file_kind,
        raw_bytes=raw_bytes,
        encoding=encoding,
        detected_separator=detected_separator,
    )
    if df is not None:
        session.df = df
        session.separator = detected_separator

    return UploadResponse(
        session_id=session.session_id,
        filename=filename,
        file_kind=file_kind,
        encoding=encoding,
        detected_separator=detected_separator,
        available_separators=list(CANDIDATE_SEPARATORS),
        raw_preview=raw_preview,
        already_parsed=already_parsed,
    )


@app.post("/api/parse", response_model=ParseResponse)
def parse_session(body: ParseRequest) -> ParseResponse:
    session = _get_session_or_404(body.session_id)

    if not body.separator:
        raise AppError(400, "MISSING_SEPARATOR", "Le séparateur est requis.")

    if session.file_kind == "csv":
        try:
            df = parse_csv(session.raw_bytes, session.encoding, body.separator)
        except ValueError as exc:
            raise AppError(400, "PARSE_ERROR", str(exc))

        if df.shape[1] <= 1:
            raise AppError(
                422,
                "SEPARATOR_LIKELY_WRONG",
                "Le séparateur choisi ne produit qu'une seule colonne. "
                "Vérifiez le séparateur sélectionné.",
            )
    elif session.df is not None:
        # Excel / JSON déjà parsés à l'upload : rien à refaire.
        df = session.df
    else:  # pragma: no cover - cas défensif
        raise AppError(400, "UNSUPPORTED_FILE_KIND", "Type de fichier non pris en charge pour le parsing.")

    session.df = df
    session.separator = body.separator
    session.touch()

    return ParseResponse(
        session_id=session.session_id,
        separator=session.separator,
        n_rows=int(df.shape[0]),
        n_columns=int(df.shape[1]),
        columns=[str(c) for c in df.columns],
        column_types=detect_column_types(df),
    )


@app.get("/api/data/{session_id}/preview")
def get_preview(session_id: str, rows: int = PREVIEW_ROWS) -> dict:
    session = _get_parsed_session_or_error(session_id)
    df = session.df
    limited = df.head(rows)
    return {
        "session_id": session_id,
        "columns": [str(c) for c in df.columns],
        "column_types": detect_column_types(df),
        "rows": dataframe_to_records(limited),
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "shown_rows": int(limited.shape[0]),
    }


@app.get("/api/stats/{session_id}")
def get_stats(session_id: str) -> dict:
    session = _get_parsed_session_or_error(session_id)
    summary = dataframe_summary(session.df)
    summary["session_id"] = session_id
    summary["filename"] = session.filename
    return summary


@app.get("/api/column/{session_id}/{col_name}/stats")
def get_column_stats(session_id: str, col_name: str) -> dict:
    session = _get_parsed_session_or_error(session_id)
    if col_name not in session.df.columns:
        raise column_not_found(col_name)
    return {
        "session_id": session_id,
        "column": col_name,
        **column_summary(session.df[col_name]),
    }
