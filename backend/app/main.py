"""DataVortex - Backend FastAPI (Phase 1 MVP + Phase 2 Visualisations).

Fonctionnalités :
- Upload de fichiers (CSV / Excel / JSON) stockés en mémoire par session
- Détection automatique de l'encoding et du séparateur (pour les CSV)
- Parsing en DataFrame pandas avec le séparateur choisi/confirmé
- Aperçu des données (100 premières lignes)
- Statistiques descriptives par colonne
- Visualisations interactives 1D / 2D / 3D (Plotly) + export PNG/SVG/HTML
"""
from __future__ import annotations

import io
import json
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, File, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.columns_service import apply_column_operation, apply_transform, describe_columns
from app.errors import (
    AppError,
    app_error_handler,
    column_not_found,
    not_parsed_yet,
    session_not_found,
    unhandled_exception_handler,
)
from app.filter_service import apply_advanced_filter
from app.filtering import evaluate_filter
from app.formulas import evaluate_formula
from app.groupby_service import run_groupby
from app.ml import run_classification, run_clustering, run_dimensionality_reduction, run_regression
from app.ml_export_service import build_metadata, build_training_notebook, export_model_file
from app.ml_neural_service import run_neural_network
from app.ml_registry import get_model, register_model
from app.models import (
    AdvancedFilterRequest,
    AdvancedPlotRequest,
    ApplyFilterRequest,
    ClassificationRequest,
    ClusteringRequest,
    ColumnOperationRequest,
    ColumnTransformRequest,
    CreateColumnRequest,
    ExportCsvRequest,
    ExportPlotRequest,
    GenerateReportRequest,
    GroupByExportRequest,
    GroupByRequest,
    HypothesisTestRequest,
    MergeRequest,
    ModelExportRequest,
    ModelMetadataRequest,
    NeuralNetworkRequest,
    ParseRequest,
    ParseResponse,
    PCARequest,
    PivotExportRequest,
    PivotRequest,
    Plot1DRequest,
    Plot2DRequest,
    Plot3DRequest,
    RegressionRequest,
    StatsExportRequest,
    TrainingScriptRequest,
    UploadResponse,
)
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
from app.pivot_service import run_pivot
from app.plotting import build_1d_figure, build_2d_figure, build_3d_figure
from app.plotting_service import build_advanced_figure
from app.profile_service import detailed_profile
from app.report import build_report
from app.serialize import dataframe_to_records
from app.session_store import Session, store
from app.stats import column_summary, dataframe_summary
from app.stats_service import advanced_stats, stats_export_table
from app.stats_tests_service import run_statistical_test
from app.table_service import read_rows

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


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict:
    """Libère une session immédiatement (ex : fermeture d'un onglet côté frontend)."""
    store.delete(session_id)
    return {"deleted": True}


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


@app.post("/api/merge")
def merge_sessions(body: MergeRequest) -> dict:
    if len(body.session_ids) < 2:
        raise AppError(400, "INSUFFICIENT_SESSIONS", "Sélectionnez au moins 2 fichiers à fusionner.")

    sessions = [_get_parsed_session_or_error(sid) for sid in body.session_ids]
    dfs = [s.active_df() for s in sessions]

    if body.mode == "concat":
        column_sets = [frozenset(df.columns) for df in dfs]
        if len(set(column_sets)) > 1:
            details = "; ".join(f"{s.filename} : {sorted(df.columns)}" for s, df in zip(sessions, dfs))
            raise AppError(
                400,
                "INCOMPATIBLE_COLUMNS",
                f"Les fichiers sélectionnés n'ont pas les mêmes colonnes, la concaténation nécessite "
                f"des schémas identiques. Colonnes trouvées — {details}",
            )
        merged = pd.concat(dfs, axis=0, ignore_index=True)
    else:
        if not body.key_column:
            raise AppError(400, "MISSING_KEY_COLUMN", "Une colonne clé est requise pour un merge.")
        if body.left_suffix == body.right_suffix:
            raise AppError(
                400,
                "INVALID_SUFFIXES",
                "Les suffixes gauche et droite doivent être différents.",
            )
        for session, df in zip(sessions, dfs):
            if body.key_column not in df.columns:
                raise AppError(
                    400,
                    "KEY_COLUMN_NOT_FOUND",
                    f"La colonne '{body.key_column}' est absente du fichier '{session.filename}'.",
                )
        merged = dfs[0]
        for df in dfs[1:]:
            try:
                merged = pd.merge(
                    merged, df, on=body.key_column, how="inner",
                    suffixes=(body.left_suffix, body.right_suffix),
                )
            except Exception as exc:
                raise AppError(400, "MERGE_FAILED", f"Échec du merge : {exc}")
        if merged.shape[0] == 0:
            raise AppError(
                422,
                "MERGE_EMPTY_RESULT",
                "Le merge ne produit aucune ligne : aucune valeur commune trouvée sur la colonne clé.",
            )

    label = f"{'Concat' if body.mode == 'concat' else 'Merge'} : " + " + ".join(s.filename for s in sessions)
    new_session = store.create(
        filename=label,
        file_kind="merged",
        raw_bytes=b"",
        encoding="utf-8",
        detected_separator=None,
    )
    new_session.df = merged
    new_session.separator = None

    return {
        "new_session_id": new_session.session_id,
        "filename": label,
        "status": "ok",
        "row_count": int(merged.shape[0]),
        "column_count": int(merged.shape[1]),
        "columns": [str(c) for c in merged.columns],
    }


@app.get("/api/data/{session_id}/preview")
def get_preview(session_id: str, rows: int = PREVIEW_ROWS) -> dict:
    session = _get_parsed_session_or_error(session_id)
    df = session.active_df()
    limited = df.head(rows)
    return {
        "session_id": session_id,
        "columns": [str(c) for c in df.columns],
        "column_types": detect_column_types(df),
        "rows": dataframe_to_records(limited),
        "total_rows": int(df.shape[0]),
        "total_columns": int(df.shape[1]),
        "shown_rows": int(limited.shape[0]),
        "filtered": session.filtered_df is not None,
        "total_rows_unfiltered": int(session.df.shape[0]),
    }


@app.get("/api/stats/{session_id}")
def get_stats(session_id: str) -> dict:
    session = _get_parsed_session_or_error(session_id)
    summary = dataframe_summary(session.active_df())
    summary["session_id"] = session_id
    summary["filename"] = session.filename
    summary["filtered"] = session.filtered_df is not None
    return summary


@app.get("/api/column/{session_id}/{col_name}/stats")
def get_column_stats(session_id: str, col_name: str) -> dict:
    session = _get_parsed_session_or_error(session_id)
    df = session.active_df()
    if col_name not in df.columns:
        raise column_not_found(col_name)
    return {
        "session_id": session_id,
        "column": col_name,
        **column_summary(df[col_name]),
    }


# --- Filtrage & Colonnes calculées (Phase 3) ---------------------------------

@app.post("/api/data/{session_id}/filter")
def apply_filter(session_id: str, body: ApplyFilterRequest) -> dict:
    session = _get_parsed_session_or_error(session_id)

    if body.filter is None:
        session.active_filter = None
        session.filtered_df = None
    else:
        mask = evaluate_filter(session.df, body.filter)
        session.active_filter = body.filter
        session.filtered_df = session.df[mask]
    session.touch()

    df = session.active_df()
    limited = df.head(PREVIEW_ROWS)
    return {
        "session_id": session_id,
        "filtered": session.filtered_df is not None,
        "columns": [str(c) for c in df.columns],
        "column_types": detect_column_types(df),
        "rows": dataframe_to_records(limited),
        "total_rows": int(df.shape[0]),
        "total_rows_unfiltered": int(session.df.shape[0]),
        "total_columns": int(df.shape[1]),
        "shown_rows": int(limited.shape[0]),
    }


@app.post("/api/data/{session_id}/columns")
def create_column(session_id: str, body: CreateColumnRequest) -> dict:
    session = _get_parsed_session_or_error(session_id)

    if not body.name.strip():
        raise AppError(400, "INVALID_COLUMN_NAME", "Le nom de la colonne est requis.")

    if body.preview_only:
        base_df = session.active_df().head(max(1, body.preview_rows))
        result, error_count = evaluate_formula(base_df, body.formula)
        return {
            "session_id": session_id,
            "preview": [None if pd.isna(v) else v for v in result.tolist()] if len(result) else [],
            "error_count": error_count,
        }

    if body.name in session.df.columns and not body.overwrite:
        raise AppError(
            409,
            "COLUMN_ALREADY_EXISTS",
            f"La colonne '{body.name}' existe déjà. Utilisez 'overwrite' pour la remplacer.",
        )

    result, error_count = evaluate_formula(session.df, body.formula)
    session.df[body.name] = result

    if session.active_filter is not None:
        mask = evaluate_filter(session.df, session.active_filter)
        session.filtered_df = session.df[mask]

    session.touch()
    df = session.active_df()

    return {
        "session_id": session_id,
        "name": body.name,
        "error_count": error_count,
        "columns": [str(c) for c in session.df.columns],
        "column_types": detect_column_types(session.df),
        "n_rows": int(session.df.shape[0]),
        "n_columns": int(session.df.shape[1]),
        "preview": dataframe_to_records(df.head(10)),
    }


# --- Visualisations (Phase 2) ------------------------------------------------

def _figure_to_response(fig) -> dict:
    """Sérialise une figure Plotly en JSON-safe via l'encodeur natif de Plotly."""
    return json.loads(fig.to_json())


@app.post("/api/plot/1d")
def plot_1d(body: Plot1DRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    fig = build_1d_figure(session.active_df(), body)
    return {"figure": _figure_to_response(fig)}


@app.post("/api/plot/2d")
def plot_2d(body: Plot2DRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    fig = build_2d_figure(session.active_df(), body)
    return {"figure": _figure_to_response(fig)}


@app.post("/api/plot/3d")
def plot_3d(body: Plot3DRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    fig = build_3d_figure(session.active_df(), body)
    return {"figure": _figure_to_response(fig)}


_PLOT_BUILDERS = {
    "1d": (Plot1DRequest, build_1d_figure),
    "2d": (Plot2DRequest, build_2d_figure),
    "3d": (Plot3DRequest, build_3d_figure),
    "advanced": (AdvancedPlotRequest, lambda df, params: build_advanced_figure(df, params)["figure"]),
}


# --- Export (Phase 4) --------------------------------------------------------

@app.post("/api/export/csv")
def export_csv(body: ExportCsvRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)
    df = session.active_df()

    if not body.separator:
        raise AppError(400, "MISSING_SEPARATOR", "Le séparateur d'export est requis.")

    buffer = io.StringIO()
    if body.include_filter_comment and session.active_filter is not None:
        filter_json = json.dumps(session.active_filter.model_dump(), ensure_ascii=False)
        buffer.write(f"# Filtre appliqué : {filter_json}\n")
    df.to_csv(buffer, sep=body.separator, index=False)
    text = buffer.getvalue()

    try:
        encoded = text.encode(body.encoding)
    except LookupError:
        raise AppError(400, "INVALID_ENCODING", f"Encoding inconnu : '{body.encoding}'.")

    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    filename = f"data_{timestamp}.csv"
    return Response(
        content=encoded,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export/plot")
def export_plot(body: ExportPlotRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)

    model_cls, builder = _PLOT_BUILDERS[body.kind]
    try:
        params = model_cls(session_id=body.session_id, **body.params)
    except Exception as exc:
        raise AppError(400, "INVALID_PLOT_PARAMS", f"Paramètres de graphique invalides : {exc}")

    fig = builder(session.active_df(), params)
    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    plot_type = body.params.get("plot_type", body.kind)
    filename = f"plot_{plot_type}_{timestamp}.{body.format}"

    if body.format == "html":
        html = fig.to_html(full_html=True, include_plotlyjs="cdn")
        return Response(
            content=html,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    try:
        image_bytes = fig.to_image(format=body.format, width=body.width, height=body.height)
    except Exception as exc:
        raise AppError(
            500,
            "EXPORT_FAILED",
            f"Échec de l'export {body.format.upper()} (moteur kaleido) : {exc}",
        )

    media_type = "image/svg+xml" if body.format == "svg" else "image/png"
    return Response(
        content=image_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Rapport PDF (Phase 6) ----------------------------------------------------

@app.post("/api/report/pdf")
def generate_report_pdf(body: GenerateReportRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)

    try:
        pdf_bytes = build_report(
            session,
            sections=body.sections,
            plot_specs=body.plots,
            page_format=body.page_format,
            orientation=body.orientation,
            resize_plots_to_fit=body.resize_plots_to_fit,
        )
    except AppError:
        raise
    except Exception as exc:
        raise AppError(500, "REPORT_GENERATION_FAILED", f"Échec de la génération du rapport : {exc}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    filename = f"rapport_{timestamp}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Machine Learning (Phase 7) -----------------------------------------------

def _finalize_ml_result(result: dict, session: Session | None = None, task: str | None = None,
                         model_type: str | None = None) -> dict:
    """Convertit les figures Plotly internes (_fig/_extra_figs) en JSON-safe
    sous une clé unique `plot_data`, pour une réponse API homogène. Si le
    résultat contient un modèle entraîné (_model/_model_meta), l'enregistre
    dans la session (Phase 8.1) et ajoute `model_id` à la réponse pour
    permettre son export a posteriori."""
    fig = result.pop("_fig")
    extra = result.pop("_extra_figs", {})
    plot_data = {"main": json.loads(fig.to_json())}
    for name, extra_fig in extra.items():
        plot_data[name] = json.loads(extra_fig.to_json())
    result["plot_data"] = plot_data

    estimator = result.pop("_model", None)
    meta = result.pop("_model_meta", None)
    if estimator is not None and meta is not None and session is not None:
        result["model_id"] = register_model(
            session, task=task, model_type=model_type, estimator=estimator, **meta,
        )
    return result


@app.post("/api/ml/regression")
def ml_regression(body: RegressionRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    result = run_regression(
        session.active_df(), body.features, body.target, body.model_type, body.degree, body.params,
    )
    return _finalize_ml_result(result, session, "regression", body.model_type)


@app.post("/api/ml/classification")
def ml_classification(body: ClassificationRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    result = run_classification(session.active_df(), body.features, body.target, body.model_type, body.params)
    return _finalize_ml_result(result, session, "classification", body.model_type)


@app.post("/api/ml/clustering")
def ml_clustering(body: ClusteringRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    result = run_clustering(session.active_df(), body.features, body.model_type, body.params, body.color_by)
    return _finalize_ml_result(result)


@app.post("/api/ml/pca")
def ml_pca(body: PCARequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    result = run_dimensionality_reduction(
        session.active_df(), body.features, body.n_components, body.method, body.color_by,
    )
    return _finalize_ml_result(result)


@app.post("/api/ml/neural_network")
def ml_neural_network(body: NeuralNetworkRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    result = run_neural_network(
        session.active_df(), body.features, body.target, body.task,
        [layer.model_dump() for layer in body.layers],
        body.optimizer, body.learning_rate, body.batch_size, body.epochs, body.validation_split,
    )
    return _finalize_ml_result(result, session, "neural_network", "mlp")


@app.post("/api/ml/export/model")
def ml_export_model(body: ModelExportRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)
    model = get_model(session, body.model_id)
    content, filename, media_type, checksum = export_model_file(model, body.format)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Model-Checksum-Md5": checksum,
        },
    )


@app.post("/api/ml/export/metadata")
def ml_export_metadata(body: ModelMetadataRequest) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    model = get_model(session, body.model_id)
    return build_metadata(model)


@app.post("/api/ml/export/training_script")
def ml_export_training_script(body: TrainingScriptRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)
    model = get_model(session, body.model_id)
    content = build_training_notebook(model)
    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    filename = f"reproduction_{model.model_type}_{timestamp}.ipynb"
    return Response(
        content=content,
        media_type="application/x-ipynb+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Statistiques avancées (Phase 8) ------------------------------------------

TABLE_MEDIA_TYPES = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "latex": "application/x-latex",
}
TABLE_EXTENSIONS = {"csv": "csv", "excel": "xlsx", "latex": "tex"}


def _table_response(table: pd.DataFrame, fmt: str, precision: int, basename: str) -> Response:
    """Sérialise un DataFrame en pièce jointe CSV, Excel ou LaTeX."""
    precision = max(0, min(10, precision))
    rounded = table.copy()
    numeric_cols = rounded.select_dtypes(include="number").columns
    rounded[numeric_cols] = rounded[numeric_cols].round(precision)

    timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
    filename = f"{basename}_{timestamp}.{TABLE_EXTENSIONS[fmt]}"

    if fmt == "csv":
        content = rounded.to_csv(index=False).encode("utf-8-sig")
    elif fmt == "excel":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            rounded.to_excel(writer, index=False, sheet_name=basename[:31] or "Export")
        content = buffer.getvalue()
    else:
        latex = rounded.to_latex(index=False, escape=True, float_format=f"%.{precision}f")
        content = latex.encode("utf-8")

    return Response(
        content=content,
        media_type=TABLE_MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/stats/{session_id}/advanced")
def get_advanced_stats(session_id: str, method: str = "pearson") -> dict:
    """Corrélations (r + p-values), distributions, normalité et données manquantes."""
    session = _get_parsed_session_or_error(session_id)
    result = advanced_stats(session.active_df(), correlation_method=method)
    result["session_id"] = session_id
    result["filename"] = session.filename
    result["filtered"] = session.filtered_df is not None
    return result


@app.post("/api/stats/export")
def export_stats_table(body: StatsExportRequest) -> Response:
    session = _get_parsed_session_or_error(body.session_id)
    table = stats_export_table(session.active_df(), body.table)
    return _table_response(table, body.format, body.precision, f"stats_{body.table}")


# --- Visualisations avancées (Phase 8) ----------------------------------------

@app.post("/api/plot/advanced")
def plot_advanced(body: AdvancedPlotRequest) -> dict:
    """Graphique enrichi : tendance + bande de confiance, repères statistiques,
    palette adaptée à la vision des couleurs, annotations et nouveaux types."""
    session = _get_parsed_session_or_error(body.session_id)
    result = build_advanced_figure(session.active_df(), body)
    return {
        "figure": _figure_to_response(result["figure"]),
        "trend": result["trend"],
        "palette": result["palette"],
    }


# --- Filtres avancés (Phase 8) -------------------------------------------------

@app.post("/api/filters/apply")
def apply_advanced_filter_route(body: AdvancedFilterRequest) -> dict:
    """Applique un filtre complexe et renvoie ses indicateurs : lignes retenues,
    contribution de chaque condition, colonnes concernées et aperçu marqué."""
    session = _get_parsed_session_or_error(body.session_id)
    return apply_advanced_filter(
        session,
        body.filter,
        invert=body.invert,
        preview_rows=body.preview_rows,
        preview_mode=body.preview_mode,
    )


# --- Lecture tabulaire paginée (Phase 8) --------------------------------------

@app.get("/api/data/{session_id}/rows")
def get_rows(
    session_id: str,
    offset: int = 0,
    limit: int = 100,
    sort_by: str | None = None,
    sort_dir: str = "asc",
    search: str = "",
    search_column: str | None = None,
    group_by: str | None = None,
) -> dict:
    """Tranche triée, recherchée et paginée du jeu de données courant."""
    session = _get_parsed_session_or_error(session_id)
    return read_rows(
        session,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        search=search,
        search_column=search_column,
        group_by=group_by,
    )


# --- Groupby & agrégations (Phase 8) -------------------------------------------

def _run_groupby_for(body) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    return run_groupby(
        session.active_df(),
        group_by=body.group_by,
        aggregations=body.aggregations,
        sort_by=body.sort_by,
        sort_ascending=body.sort_ascending,
        limit=body.limit,
    )


@app.post("/api/groupby")
def groupby(body: GroupByRequest) -> dict:
    """Agrège une ou plusieurs colonnes par groupe, avec tableau et graphique."""
    result = _run_groupby_for(body)
    result.pop("table")
    figure = result.pop("figure")
    result["figure"] = _figure_to_response(figure) if figure is not None else None
    return result


@app.post("/api/groupby/export")
def export_groupby(body: GroupByExportRequest) -> Response:
    result = _run_groupby_for(body)
    return _table_response(result["table"], body.format, body.precision, "groupby")


# --- Tableaux croisés dynamiques (Phase 8) -------------------------------------

def _run_pivot_for(body) -> dict:
    session = _get_parsed_session_or_error(body.session_id)
    return run_pivot(
        session.active_df(),
        index=body.index,
        columns=body.columns,
        values=body.values or "",
        aggfunc=body.aggfunc,
        margins=body.margins,
        percentage=body.percentage,
    )


@app.post("/api/pivot")
def pivot(body: PivotRequest) -> dict:
    """Tableau croisé dynamique, avec totaux, pourcentages et heatmap associée."""
    result = _run_pivot_for(body)
    result.pop("table")
    figure = result.pop("figure")
    result["figure"] = _figure_to_response(figure) if figure is not None else None
    return result


@app.post("/api/pivot/export")
def export_pivot(body: PivotExportRequest) -> Response:
    result = _run_pivot_for(body)
    return _table_response(result["table"], body.format, body.precision, "pivot")


# --- Profilage détaillé (Phase 8) ----------------------------------------------

@app.get("/api/profile/{session_id}/detailed")
def get_detailed_profile(session_id: str) -> dict:
    """Profil par colonne, score de qualité, doublons, anomalies et suggestions."""
    session = _get_parsed_session_or_error(session_id)
    result = detailed_profile(session.active_df())
    result["session_id"] = session_id
    result["filename"] = session.filename
    result["filtered"] = session.filtered_df is not None
    return result


# --- Tests statistiques (Phase 8) ----------------------------------------------

@app.post("/api/stats/hypothesis_test")
def hypothesis_test(body: HypothesisTestRequest) -> dict:
    """Test statistique : comparaison de groupes, ANOVA, corrélation ou ajustement.
    Renvoie statistique, p-value, taille d'effet, interprétation et visualisation."""
    session = _get_parsed_session_or_error(body.session_id)
    result = run_statistical_test(session.active_df(), body)
    figure = result.pop("_figure", None)
    result["figure"] = _figure_to_response(figure) if figure is not None else None
    return result


# --- Opérations sur les colonnes (Phase 8) -------------------------------------

@app.get("/api/columns/{session_id}")
def list_columns(session_id: str) -> dict:
    """Inventaire des colonnes : type, complétude, cardinalité et échantillon."""
    session = _get_parsed_session_or_error(session_id)
    return describe_columns(session)


@app.post("/api/columns/operation")
def column_operation(body: ColumnOperationRequest) -> dict:
    """Renomme, duplique, supprime ou réordonne des colonnes."""
    session = _get_parsed_session_or_error(body.session_id)
    return apply_column_operation(session, body.op, body.columns, body.new_name, body.order)


@app.post("/api/columns/transform")
def column_transform(body: ColumnTransformRequest) -> dict:
    """Dérive une colonne : découpage en classes, encodage, décalage, fenêtre glissante."""
    session = _get_parsed_session_or_error(body.session_id)
    return apply_transform(session, body.transform, body.source, body.params, body.new_name, body.replace)
