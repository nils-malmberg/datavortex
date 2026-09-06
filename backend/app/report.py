"""Génération de rapports PDF (Phase 6) avec reportlab.

Le rapport combine toujours une page de couverture, puis les sections
sélectionnées par l'utilisateur (résumé exécutif, statistiques, aperçu des
données, graphiques, corrélations, métadonnées). Les graphiques (et la
heatmap de corrélation) sont regénérés côté serveur à partir de leur
spécification (même mécanisme que POST /api/plot/*) puis rendus en image PNG
via kaleido pour être intégrés au PDF — cela garantit qu'ils sont toujours
mis à l'échelle pour tenir dans les marges de page, quel que soit le nombre
de colonnes numériques. Les tableaux (stats, aperçu, métadonnées) ont des
largeurs de colonnes explicites calées sur la largeur de contenu de la page
et enveloppent leur texte dans des Paragraph, pour ne jamais dépasser les
marges même avec des valeurs longues.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus import Image as RLImage

from app.errors import AppError
from app.groupby_service import run_groupby
from app.ml import run_classification, run_clustering, run_dimensionality_reduction, run_regression
from app.models import AdvancedPlotRequest, GroupByRequest, PivotRequest, Plot1DRequest, Plot2DRequest, Plot3DRequest
from app.parsing import detect_column_types
from app.pivot_service import run_pivot
from app.plotting import build_1d_figure, build_2d_figure, build_3d_figure
from app.plotting_service import build_advanced_figure
from app.profile_service import detailed_profile
from app.stats import dataframe_summary
from app.stats_service import advanced_stats

PAGE_SIZES = {"A4": A4, "Letter": LETTER}

_PLOT_BUILDERS = {
    "1d": (Plot1DRequest, build_1d_figure),
    "2d": (Plot2DRequest, build_2d_figure),
    "3d": (Plot3DRequest, build_3d_figure),
    "advanced": (AdvancedPlotRequest, lambda df, params: build_advanced_figure(df, params)["figure"]),
}

# Chaque runner ML prend (df, params_dict) et retourne un dict avec une clé
# interne "_fig" (figure Plotly principale) -- réutilisé tel quel pour
# intégrer une analyse ML au rapport, sans dupliquer la logique des routes
# /api/ml/*.
_ML_RUNNERS = {
    "regression": lambda df, p: run_regression(
        df, p["features"], p["target"], p.get("model_type", "linear"), p.get("degree", 2),
    ),
    "classification": lambda df, p: run_classification(
        df, p["features"], p["target"], p.get("model_type", "logistic"), p.get("params", {}),
    ),
    "clustering": lambda df, p: run_clustering(
        df, p["features"], p.get("model_type", "kmeans"), p.get("params", {}), p.get("color_by"),
    ),
    "pca": lambda df, p: run_dimensionality_reduction(
        df, p["features"], p.get("n_components", 2), p.get("method", "pca"), p.get("color_by"),
    ),
}

# Philosophie Phase 8.1 : le résumé, les statistiques détaillées (avec
# corrélations et qualité des données) et les suggestions sont TOUJOURS
# inclus, quel que soit le contenu de `sections` — seuls l'aperçu des
# données/métadonnées (hérités de la Phase 6) et les graphiques/analyses
# ajoutés par l'utilisateur restent sélectionnables.

_BRAND = colors.HexColor("#2563eb")
_MUTED = colors.HexColor("#64748b")
_BORDER = colors.HexColor("#e2e8f0")
_HEADER_BG = colors.HexColor("#f1f5f9")


def _page_size(page_format: str, orientation: str):
    size = PAGE_SIZES.get(page_format, A4)
    if orientation == "landscape":
        size = landscape(size)
    return size


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontSize=28, leading=34, textColor=_BRAND, spaceAfter=6))
    styles.add(ParagraphStyle(name="CoverSubtitle", fontSize=14, leading=18, textColor=_MUTED, spaceAfter=24))
    styles.add(ParagraphStyle(name="CoverMeta", fontSize=11, leading=16, textColor=colors.HexColor("#1e293b")))
    styles.add(ParagraphStyle(name="SectionHeading", fontSize=16, leading=20, textColor=_BRAND, spaceBefore=6, spaceAfter=10))
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14, textColor=colors.HexColor("#334155")))
    styles.add(ParagraphStyle(name="PlotCaption", fontSize=9, leading=12, textColor=_MUTED, spaceBefore=4, spaceAfter=16))
    styles.add(ParagraphStyle(name="CellText", fontSize=8, leading=10, textColor=colors.HexColor("#334155"), wordWrap="CJK"))
    styles.add(ParagraphStyle(name="CellHeader", fontSize=8, leading=10, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold"))
    return styles


def _cell(text, style) -> Paragraph:
    """Enveloppe une valeur de cellule dans un Paragraph pour qu'elle puisse
    passer à la ligne au lieu de forcer le tableau à dépasser sa largeur."""
    safe = "" if text is None else str(text)
    safe = safe.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def _header_footer(session):
    def draw(canvas, doc):
        canvas.saveState()
        width, height = doc.pagesize
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(_MUTED)
        canvas.drawString(2 * cm, height - 1.3 * cm, "DataVortex — Rapport de données")
        canvas.drawRightString(width - 2 * cm, height - 1.3 * cm, session.filename)
        canvas.setStrokeColor(_BORDER)
        canvas.line(2 * cm, height - 1.45 * cm, width - 2 * cm, height - 1.45 * cm)
        canvas.line(2 * cm, 1.5 * cm, width - 2 * cm, 1.5 * cm)
        canvas.drawCentredString(width / 2, 1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def _cover_flowables(session, df, styles):
    n_rows, n_cols = df.shape
    filter_note = "Oui" if session.filtered_df is not None else "Non"
    return [
        Spacer(1, 4 * cm),
        Paragraph("DataVortex", styles["CoverTitle"]),
        Paragraph("Rapport d'analyse de données", styles["CoverSubtitle"]),
        Spacer(1, 1 * cm),
        Paragraph(f"<b>Fichier :</b> {session.filename}", styles["CoverMeta"]),
        Paragraph(f"<b>Généré le :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["CoverMeta"]),
        Paragraph(f"<b>Lignes :</b> {n_rows} &nbsp;&nbsp; <b>Colonnes :</b> {n_cols}", styles["CoverMeta"]),
        Paragraph(f"<b>Filtre actif :</b> {filter_note}", styles["CoverMeta"]),
    ]


def _summary_flowables(session, df, styles, content_width, profile):
    types = detect_column_types(df)
    type_counts: dict[str, int] = {}
    for t in types.values():
        type_counts[t] = type_counts.get(t, 0) + 1
    type_line = ", ".join(f"{count} {name}" for name, count in sorted(type_counts.items()))
    summary = dataframe_summary(df)
    quality = profile["quality"]

    story = [Paragraph("Résumé exécutif", styles["SectionHeading"])]
    rows = [
        ["Lignes", str(summary["n_rows"])],
        ["Colonnes", str(summary["n_columns"])],
        ["Types de colonnes", type_line],
        ["Taille en mémoire", f"{summary['memory_usage_bytes'] / 1024:.1f} KB"],
        ["Session filtrée", "Oui" if session.filtered_df is not None else "Non"],
        ["Score de qualité", f'{quality["score"]}/100 — {quality["grade"]}'],
    ]
    story.append(_kv_table(rows, styles, content_width))
    story.append(Spacer(1, 0.6 * cm))
    return story


def _metadata_flowables(session, styles, content_width):
    story = [Paragraph("Métadonnées", styles["SectionHeading"])]
    rows = [
        ["Nom du fichier", session.filename],
        ["Type de fichier", session.file_kind],
        ["Encoding", session.encoding],
        ["Séparateur", repr(session.separator) if session.separator else "—"],
    ]
    if session.filtered_df is not None and session.active_filter is not None:
        rows.append(["Filtre appliqué", _describe_filter(session.active_filter)])
        rows.append(["Lignes après filtre", f"{session.filtered_df.shape[0]} / {session.df.shape[0]}"])
    story.append(_kv_table(rows, styles, content_width))
    story.append(Spacer(1, 0.6 * cm))
    return story


def _describe_filter(node) -> str:
    if node is None:
        return "—"
    if node.type == "condition":
        return f"{node.column} {node.operator} {node.value!r}"
    parts = [_describe_filter(c) for c in node.conditions]
    return f" {node.logic} ".join(f"({p})" for p in parts)


def _kv_table(rows: list[list[str]], styles, content_width: float) -> Table:
    label_width = 4.5 * cm
    value_width = max(content_width - label_width, 3 * cm)
    body = [[_cell(label, styles["CellHeader"]), _cell(value, styles["CellText"])] for label, value in rows]
    table = Table(body, colWidths=[label_width, value_width])
    table.setStyle(
        TableStyle(
            [
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _quality_tone_hex(score: float) -> str:
    if score >= 90:
        return "#16a34a"
    if score >= 70:
        return "#d97706"
    return "#dc2626"


def _numeric_stats_table(stats_summary: dict, profile_by_col: dict, styles, content_width) -> Table:
    header = ["Colonne", "Moy.", "Méd.", "É.-T.", "CV (%)", "Min", "Q1", "Q3", "Max", "Asym."]
    col_widths = [content_width * w for w in (0.18, 0.09, 0.09, 0.10, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09)]
    rows = [[_cell(h, styles["CellHeader"]) for h in header]]

    def fmt(v):
        return "—" if v is None else f"{v:.3g}"

    for col, stats in stats_summary.items():
        skew = profile_by_col.get(col, {}).get("skewness")
        rows.append([
            _cell(col, styles["CellText"]),
            _cell(fmt(stats.get("mean")), styles["CellText"]),
            _cell(fmt(stats.get("median")), styles["CellText"]),
            _cell(fmt(stats.get("std")), styles["CellText"]),
            _cell(fmt(stats.get("cv_percent")), styles["CellText"]),
            _cell(fmt(stats.get("min")), styles["CellText"]),
            _cell(fmt(stats.get("q1")), styles["CellText"]),
            _cell(fmt(stats.get("q3")), styles["CellText"]),
            _cell(fmt(stats.get("max")), styles["CellText"]),
            _cell(fmt(skew), styles["CellText"]),
        ])
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _categorical_stats_table(categorical_cols, profile_by_col, styles, content_width) -> Table:
    header = ["Colonne", "Cardinalité", "Mode", "Top valeurs"]
    col_widths = [content_width * w for w in (0.2, 0.15, 0.2, 0.45)]
    rows = [[_cell(h, styles["CellHeader"]) for h in header]]
    for col in categorical_cols:
        prof = profile_by_col.get(col, {})
        top = ", ".join(f"{v['value']} ({v['count']})" for v in prof.get("top_values", [])[:5])
        rows.append([
            _cell(col, styles["CellText"]),
            _cell(prof.get("unique", "—"), styles["CellText"]),
            _cell(prof.get("mode", "—"), styles["CellText"]),
            _cell(top or "—", styles["CellText"]),
        ])
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _top_correlations_table(correlations: dict, styles, content_width) -> Table | None:
    cols = correlations.get("columns") or []
    matrix = correlations.get("matrix") or []
    pvalues = correlations.get("p_values") or []
    if len(cols) < 2:
        return None
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = matrix[i][j]
            if r is None:
                continue
            pairs.append((abs(r), cols[i], cols[j], r, pvalues[i][j]))
    pairs.sort(key=lambda t: t[0], reverse=True)

    header = ["Paire de colonnes", "r", "p-value"]
    col_widths = [content_width * 0.6, content_width * 0.2, content_width * 0.2]
    rows = [[_cell(h, styles["CellHeader"]) for h in header]]
    for _, a, b, r, p in pairs[:5]:
        p_text = "< 0.001" if p is not None and p < 0.001 else (f"{p:.3f}" if p is not None else "—")
        rows.append([_cell(f"{a} ↔ {b}", styles["CellText"]), _cell(f"{r:.3f}", styles["CellText"]), _cell(p_text, styles["CellText"])])
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    return table


def _detailed_stats_flowables(df, styles, content_width, resize_to_fit: bool, stats, profile):
    """Section statistique toujours incluse (Phase 8.1) : réutilise les mêmes
    calculs que les onglets Stats/Profil de l'application (advanced_stats,
    detailed_profile) plutôt que de les refaire, pour rester cohérent avec ce
    que l'utilisateur voit à l'écran."""
    types = detect_column_types(df)
    numeric_cols = [c for c in df.columns if types[c] in ("integer", "float")]
    categorical_cols = [c for c in df.columns if c not in numeric_cols]

    profile_by_col = profile["profile"]
    quality = profile["quality"]

    story = [Paragraph("Statistiques détaillées", styles["SectionHeading"])]

    # Qualité des données : score global + détail par dimension.
    story.append(Paragraph(
        f'<b>Score de qualité : <font color="{_quality_tone_hex(quality["score"])}">'
        f'{quality["score"]}/100 — {quality["grade"]}</font></b>',
        styles["Body"],
    ))
    story.append(Spacer(1, 0.2 * cm))
    quality_rows = [[_cell(h, styles["CellHeader"]) for h in ["Dimension", "Score", "Détail"]]]
    for dim in quality["dimensions"].values():
        quality_rows.append([
            _cell(dim["label"], styles["CellText"]),
            _cell(f"{dim['score']}%", styles["CellText"]),
            _cell(dim["detail"], styles["CellText"]),
        ])
    quality_table = Table(quality_rows, colWidths=[3.5 * cm, 2 * cm, content_width - 5.5 * cm], repeatRows=1)
    quality_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
    ]))
    story.append(quality_table)
    story.append(Spacer(1, 0.5 * cm))

    if numeric_cols:
        story.append(Paragraph("Colonnes numériques", styles["Body"]))
        story.append(Spacer(1, 0.1 * cm))
        story.append(_numeric_stats_table(stats["summary"], profile_by_col, styles, content_width))
        story.append(Spacer(1, 0.5 * cm))

    if categorical_cols:
        story.append(Paragraph("Colonnes catégorielles", styles["Body"]))
        story.append(Spacer(1, 0.1 * cm))
        story.append(_categorical_stats_table(categorical_cols, profile_by_col, styles, content_width))
        story.append(Spacer(1, 0.5 * cm))

    if len(numeric_cols) >= 2:
        story.append(Paragraph("Corrélations", styles["Body"]))
        story.append(Spacer(1, 0.1 * cm))
        heatmap_request = Plot2DRequest(session_id="report", plot_type="heatmap", columns=numeric_cols)
        fig = build_2d_figure(df, heatmap_request)
        side = max(500, min(1100, 90 * len(numeric_cols)))
        png_bytes = fig.to_image(format="png", width=side, height=side, scale=1)
        scale_factor = 0.7 if resize_to_fit else 0.85
        image_width = content_width * scale_factor
        image = RLImage(io.BytesIO(png_bytes), width=image_width, height=image_width)
        image.hAlign = "LEFT"
        story.append(image)
        story.append(Spacer(1, 0.3 * cm))
        top_table = _top_correlations_table(stats["correlations"], styles, content_width)
        if top_table is not None:
            story.append(Paragraph("Corrélations les plus fortes", styles["Body"]))
            story.append(Spacer(1, 0.1 * cm))
            story.append(top_table)
        story.append(Spacer(1, 0.5 * cm))

    missing = stats["missing"]
    missing_with_gaps = [c for c in missing.get("by_column", []) if c.get("missing_count", 0) > 0]
    if missing_with_gaps:
        story.append(Paragraph("Données manquantes", styles["Body"]))
        story.append(Spacer(1, 0.1 * cm))
        rows = [[_cell(h, styles["CellHeader"]) for h in ["Colonne", "Manquants", "%"]]]
        for c in sorted(missing_with_gaps, key=lambda c: c["missing_pct"], reverse=True):
            rows.append([_cell(c["column"], styles["CellText"]), _cell(c["missing_count"], styles["CellText"]), _cell(f"{c['missing_pct']}%", styles["CellText"])])
        table = Table(rows, colWidths=[content_width * 0.5, content_width * 0.25, content_width * 0.25], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5 * cm))

    return story


def _suggestions_flowables(styles, content_width, profile):
    story = [Paragraph("Suggestions", styles["SectionHeading"])]
    suggestions = profile["suggestions"]
    if not suggestions:
        story.append(Paragraph("Aucune suggestion : le jeu de données ne présente pas de problème notable détecté.", styles["Body"]))
        story.append(Spacer(1, 0.6 * cm))
        return story
    for s in suggestions:
        story.append(Paragraph(f'<b>[{s["priority"].upper()}] {s["title"]}</b> — {s["detail"]}', styles["Body"]))
        story.append(Spacer(1, 0.1 * cm))
    story.append(Spacer(1, 0.6 * cm))
    return story


def _preview_flowables(df, styles, content_width, max_rows: int = 15, max_cols: int = 8):
    story = [Paragraph("Aperçu des données", styles["SectionHeading"])]
    columns = list(df.columns[:max_cols])
    note = ""
    if len(df.columns) > max_cols:
        note = f" (colonnes limitées à {max_cols} sur {len(df.columns)})"

    col_width = max(content_width / len(columns), 1.5 * cm)
    header = [_cell(c, styles["CellHeader"]) for c in columns]
    rows = [header]
    for _, row in df[columns].head(max_rows).iterrows():
        rows.append([_cell("" if pd.isna(v) else v, styles["CellText"]) for v in row.tolist()])

    table = Table(rows, colWidths=[col_width] * len(columns), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
            ]
        )
    )
    story.append(Paragraph(f"{min(max_rows, len(df))} premières lignes sur {len(df)}{note}", styles["Body"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(table)
    story.append(Spacer(1, 0.6 * cm))
    return story


def _build_plot_figure(df, spec):
    if spec.kind == "ml":
        ml_type = spec.params.get("ml_type")
        runner = _ML_RUNNERS.get(ml_type)
        if not runner:
            raise AppError(400, "UNKNOWN_ML_TYPE", f"Type d'analyse ML inconnu pour le rapport : {ml_type}")
        result = runner(df, spec.params)
        return result["_fig"]

    if spec.kind == "groupby":
        body = GroupByRequest(session_id="report", **spec.params)
        result = run_groupby(df, body.group_by, body.aggregations, body.sort_by, body.sort_ascending, body.limit)
        return result["figure"]

    if spec.kind == "pivot":
        body = PivotRequest(session_id="report", **spec.params)
        result = run_pivot(df, body.index, body.columns, body.values, body.aggfunc, body.margins, body.percentage)
        return result["figure"]

    model_cls, builder = _PLOT_BUILDERS[spec.kind]
    try:
        params = model_cls(session_id="report", **spec.params)
    except Exception as exc:
        raise AppError(400, "INVALID_PLOT_PARAMS", f"Paramètres de graphique invalides pour le rapport : {exc}")
    return builder(df, params)


def _plots_flowables(df, plot_specs, styles, content_width, resize_to_fit: bool):
    story = [Paragraph("Graphiques", styles["SectionHeading"])]
    if not plot_specs:
        story.append(Paragraph("Aucun graphique sélectionné pour ce rapport.", styles["Body"]))
        story.append(Spacer(1, 0.6 * cm))
        return story

    scale_factor = 0.85 if resize_to_fit else 1.0
    image_width = content_width * scale_factor
    for i, spec in enumerate(plot_specs, start=1):
        fig = _build_plot_figure(df, spec)
        png_bytes = fig.to_image(format="png", width=1000, height=650, scale=1)
        image = RLImage(io.BytesIO(png_bytes), width=image_width, height=image_width * 0.65)
        image.hAlign = "LEFT"
        caption = spec.title or spec.params.get("plot_type", spec.kind)
        story.append(image)
        story.append(Paragraph(f"Graphique {i} — {caption}", styles["PlotCaption"]))
    return story


def build_report(
    session,
    sections: list[str],
    plot_specs: list,
    page_format: str,
    orientation: str,
    resize_plots_to_fit: bool = True,
) -> bytes:
    df = session.active_df()
    if df.shape[0] == 0:
        raise AppError(422, "EMPTY_DATASET", "Impossible de générer un rapport : le jeu de données actif est vide.")

    buffer = io.BytesIO()
    pagesize = _page_size(page_format, orientation)

    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=f"Rapport DataVortex — {session.filename}",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=_header_footer(session))])

    content_width = doc.width  # largeur de contenu disponible, marges déjà déduites
    styles = _styles()
    profile = detailed_profile(df)
    stats = advanced_stats(df)

    story: list = list(_cover_flowables(session, df, styles))
    story.append(PageBreak())

    # Toujours inclus (Phase 8.1) : résumé exécutif, statistiques détaillées
    # (numériques/catégorielles/corrélations/qualité/manquants) et suggestions.
    story.extend(_summary_flowables(session, df, styles, content_width, profile))
    if "metadata" in sections:
        story.extend(_metadata_flowables(session, styles, content_width))
    story.append(PageBreak())
    story.extend(_detailed_stats_flowables(df, styles, content_width, resize_plots_to_fit, stats, profile))
    story.extend(_suggestions_flowables(styles, content_width, profile))

    if "preview" in sections:
        story.append(PageBreak())
        story.extend(_preview_flowables(df, styles, content_width))

    if plot_specs:
        story.append(PageBreak())
        story.extend(_plots_flowables(df, plot_specs, styles, content_width, resize_plots_to_fit))

    doc.build(story)
    return buffer.getvalue()
