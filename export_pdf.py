"""PDF export for HumanWrite AI v1 (reportlab platypus)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from nlp import split_paragraphs

_ACCENT = colors.HexColor("#5b21b6")


def _styles():
    ss = getSampleStyleSheet()
    title = ParagraphStyle("HWTitle", parent=ss["Title"], textColor=_ACCENT,
                           fontSize=20, spaceAfter=6)
    sub = ParagraphStyle("HWSub", parent=ss["Normal"], textColor=colors.grey,
                         fontSize=10, spaceAfter=12)
    body = ParagraphStyle("HWBody", parent=ss["Normal"], fontSize=11,
                          leading=15, spaceAfter=8)
    cell = ParagraphStyle("HWCell", parent=ss["Normal"], fontSize=9, leading=12)
    cellh = ParagraphStyle("HWCellH", parent=cell, textColor=colors.white,
                           fontName="Helvetica-Bold")
    return title, sub, body, cell, cellh


def export_pdf(title: str, text: str, kind: str = "revised",
               original_text: str = "") -> bytes:
    """Build a PDF in memory and return its bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    title_s, sub_s, body_s, cell_s, cellh_s = _styles()
    story = []

    if kind == "comparison":
        story.append(Paragraph(title or "Untitled", title_s))
        story.append(Paragraph("HumanWrite AI — side-by-side comparison report",
                               sub_s))
        story.append(Paragraph(
            "Left column shows the original paragraph; right column shows the "
            "revised paragraph. Paragraphs are aligned by position.", body_s))
        orig_paras = split_paragraphs(original_text)
        new_paras = split_paragraphs(text)
        rows = [[Paragraph("<b>Original</b>", cellh_s),
                 Paragraph("<b>Revised</b>", cellh_s)]]
        for i in range(max(len(orig_paras), len(new_paras))):
            o = orig_paras[i] if i < len(orig_paras) else ""
            n = new_paras[i] if i < len(new_paras) else ""
            rows.append([Paragraph(o.replace("&", "&amp;"), cell_s),
                         Paragraph(n.replace("&", "&amp;"), cell_s)])
        table = Table(rows, colWidths=[8 * cm, 8 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
    else:
        label = "Original text" if kind == "original" else "Revised text"
        story.append(Paragraph(title or "Untitled", title_s))
        story.append(Paragraph(f"HumanWrite AI — {label} (exported locally)",
                               sub_s))
        for para in split_paragraphs(text):
            story.append(Paragraph(para.replace("&", "&amp;"), body_s))

    story.append(Spacer(1, 12))
    doc.build(story)
    return buf.getvalue()


def validate_pdf(data: bytes) -> dict:
    """Check the bytes open as a real PDF with extractable text."""
    checks = []
    ok = True
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        pages = len(reader.pages)
        checks.append({"name": "opens_as_pdf", "passed": True,
                       "detail": f"{pages} page(s)"})
        text = "".join((p.extract_text() or "") for p in reader.pages)
        has_text = len(text.strip()) > 20
        checks.append({"name": "text_extractable", "passed": has_text,
                       "detail": f"{len(text.strip())} chars extracted"})
        ok = has_text
    except Exception as exc:  # noqa: BLE001 — validation must not raise
        checks.append({"name": "opens_as_pdf", "passed": False,
                       "detail": str(exc)[:200]})
        ok = False
    return {"ok": ok, "checks": checks}
