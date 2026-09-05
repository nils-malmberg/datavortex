"""Génération de rapports PDF (Phase 6) avec reportlab.

Le rapport combine toujours une page de couverture, puis les sections
sélectionnées par l'utilisateur (résumé exécutif, statistiques, aperçu des
données, graphiques, corrélations, métadonnées). Les graphiques sont
regénérés côté serveur à partir de leur spécification (même mécanisme que
POST /api/plot/*) puis rendus en image PNG via kaleido pour être intégrés au
PDF.
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
from app.models import Plot1DRequest, Plot2DRequest, Plot3DRequest
from app.parsing import detect_column_types
from app.plotting import build_1d_figure, build_2d_figure, build_3d_figure
from app.stats import column_summary, dataframe_summary

PAGE_SIZES = {"A4": A4, "Letter": LETTER}

_PLOT_BUILDERS = {
    "1d": (Plot1DRequest, build_1d_figure),
    "2d": (Plot2DRequest, build_2d_figure),
    "3d": (Plot3DRequest, build_3d_figure),
}

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
    return styles


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


def _summary_flowables(session, df, styles):
    types = detect_column_types(df)
    type_counts: dict[str, int] = {}
    for t in types.values():
        type_counts[t] = type_counts.get(t, 0) + 1
    type_line = ", ".join(f"{count} {name}" for name, count in sorted(type_counts.items()))
    summary = dataframe_summary(df)

    story = [Paragraph("Résumé exécutif", styles["SectionHeading"])]
    rows = [
        ["Lignes", str(summary["n_rows"])],
        ["Colonnes", str(summary["n_columns"])],
        ["Types de colonnes", type_line],
        ["Taille en mémoire", f"{summary['memory_usage_bytes'] / 1024:.1f} KB"],
        ["Session filtrée", "Oui" if session.filtered_df is not None else "Non"],
    ]
    story.append(_kv_table(rows))
    story.append(Spacer(1, 0.6 * cm))
    return story


def _metadata_flowables(session, styles):
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
    story.append(_kv_table(rows))
    story.append(Spacer(1, 0.6 * cm))
    return story


def _describe_filter(node) -> str:
    if node is None:
        return "—"
    if node.type == "condition":
        return f"{node.column} {node.operator} {node.value!r}"
    parts = [_describe_filter(c) for c in node.conditions]
    return f" {node.logic} ".join(f"({p})" for p in parts)


def _kv_table(rows: list[list[str]]) -> Table:
    table = Table(rows, colWidths=[4.5 * cm, None])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _format_stat_summary(col_type: str, stats: dict) -> str:
    if col_type in ("integer", "float"):
        mean, std = stats.get("mean"), stats.get("std")
        if mean is None:
            return "—"
        return f"moyenne {mean:.2f}, écart-type {std:.2f}" if std is not None else f"moyenne {mean:.2f}"
    if col_type == "boolean":
        return f"vrai : {stats.get('pct_true', 0)}%"
    mode = stats.get("mode")
    unique = stats.get("unique")
    return f"{unique} valeurs uniques, mode : {mode}" if mode is not None else f"{unique} valeurs uniques"


def _stats_flowables(df, styles):
    story = [Paragraph("Statistiques par colonne", styles["SectionHeading"])]
    header = ["Colonne", "Type", "Count", "Manquants", "Résumé"]
    rows = [header]
    for col in df.columns:
        summary = column_summary(df[col])
        rows.append(
            [
                col,
                summary["type"],
                str(summary["stats"].get("count", "—")),
                f"{summary['missing_pct']}%",
                _format_stat_summary(summary["type"], summary["stats"]),
            ]
        )
    table = Table(rows, colWidths=[3.2 * cm, 2 * cm, 1.8 * cm, 2.2 * cm, None], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.6 * cm))
    return story


def _preview_flowables(df, styles, max_rows: int = 15, max_cols: int = 8):
    story = [Paragraph("Aperçu des données", styles["SectionHeading"])]
    columns = list(df.columns[:max_cols])
    note = ""
    if len(df.columns) > max_cols:
        note = f" (colonnes limitées à {max_cols} sur {len(df.columns)})"
    header = columns
    rows = [header]
    for _, row in df[columns].head(max_rows).iterrows():
        rows.append([("" if pd.isna(v) else str(v)) for v in row.tolist()])
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
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


def _correlation_color(value: float) -> colors.Color:
    value = max(-1.0, min(1.0, value))
    if value >= 0:
        return colors.Color(1 - value * 0.6, 1 - value * 0.25, 1 - value * 0.05)
    v = -value
    return colors.Color(1 - v * 0.05, 1 - v * 0.25, 1 - v * 0.6)


def _correlations_flowables(df, styles):
    story = [Paragraph("Corrélations", styles["SectionHeading"])]
    types = detect_column_types(df)
    numeric_cols = [c for c in df.columns if types[c] in ("integer", "float")]
    if len(numeric_cols) < 2:
        story.append(Paragraph("Pas assez de colonnes numériques pour calculer des corrélations.", styles["Body"]))
        story.append(Spacer(1, 0.6 * cm))
        return story

    corr = df[numeric_cols].corr()
    header = [""] + numeric_cols
    rows = [header]
    for row_name in numeric_cols:
        rows.append([row_name] + [f"{corr.loc[row_name, c]:.2f}" for c in numeric_cols])

    table = Table(rows, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("BACKGROUND", (0, 0), (0, -1), _HEADER_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, _BORDER),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]
    for i, row_name in enumerate(numeric_cols):
        for j, col_name in enumerate(numeric_cols):
            style_cmds.append(("BACKGROUND", (j + 1, i + 1), (j + 1, i + 1), _correlation_color(corr.loc[row_name, col_name])))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(Spacer(1, 0.6 * cm))
    return story


def _build_plot_figure(df, spec):
    model_cls, builder = _PLOT_BUILDERS[spec.kind]
    try:
        params = model_cls(session_id="report", **spec.params)
    except Exception as exc:
        raise AppError(400, "INVALID_PLOT_PARAMS", f"Paramètres de graphique invalides pour le rapport : {exc}")
    return builder(df, params)


def _plots_flowables(df, plot_specs, styles, page_width):
    story = [Paragraph("Graphiques", styles["SectionHeading"])]
    if not plot_specs:
        story.append(Paragraph("Aucun graphique sélectionné pour ce rapport.", styles["Body"]))
        story.append(Spacer(1, 0.6 * cm))
        return story

    image_width = page_width - 4 * cm
    for i, spec in enumerate(plot_specs, start=1):
        fig = _build_plot_figure(df, spec)
        png_bytes = fig.to_image(format="png", width=1000, height=650, scale=1)
        image = RLImage(io.BytesIO(png_bytes), width=image_width, height=image_width * 0.65)
        caption = spec.title or spec.params.get("plot_type", spec.kind)
        story.append(image)
        story.append(Paragraph(f"Graphique {i} — {caption}", styles["PlotCaption"]))
    return story


def build_report(session, sections: list[str], plot_specs: list, page_format: str, orientation: str) -> bytes:
    df = session.active_df()
    if df.shape[0] == 0:
        raise AppError(422, "EMPTY_DATASET", "Impossible de générer un rapport : le jeu de données actif est vide.")

    buffer = io.BytesIO()
    pagesize = _page_size(page_format, orientation)
    width, _height = pagesize

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

    styles = _styles()
    story: list = list(_cover_flowables(session, df, styles))
    story.append(PageBreak())

    section_builders = {
        "summary": lambda: _summary_flowables(session, df, styles),
        "metadata": lambda: _metadata_flowables(session, styles),
        "preview": lambda: _preview_flowables(df, styles),
        "stats": lambda: _stats_flowables(df, styles),
        "correlations": lambda: _correlations_flowables(df, styles),
        "plots": lambda: _plots_flowables(df, plot_specs, styles, width),
    }
    for key in sections:
        builder = section_builders.get(key)
        if builder:
            story.extend(builder())

    doc.build(story)
    return buffer.getvalue()
