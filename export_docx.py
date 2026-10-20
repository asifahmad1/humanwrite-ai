"""DOCX export for HumanWrite AI v1 (python-docx, native editable objects)."""

from __future__ import annotations

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from nlp import split_paragraphs

_ACCENT = RGBColor(0x5B, 0x21, 0xB6)  # violet-700


def _add_title(doc: Document, title: str, subtitle: str) -> None:
    heading = doc.add_heading(title or "Untitled", level=1)
    for run in heading.runs:
        run.font.color.rgb = _ACCENT
    sub = doc.add_paragraph(subtitle)
    sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in sub.runs:
        run.font.size = Pt(10)
        run.font.italic = True
        run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)


def _add_body(doc: Document, text: str) -> None:
    for para in split_paragraphs(text):
        p = doc.add_paragraph(para)
        p.paragraph_format.space_after = Pt(8)
        for run in p.runs:
            run.font.size = Pt(11)


def export_docx(title: str, text: str, kind: str = "revised",
                original_text: str = "") -> bytes:
    """Build a DOCX in memory and return its bytes.

    kind: 'revised' | 'original' | 'comparison'.
    """
    from io import BytesIO

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    if kind == "comparison":
        _add_title(doc, title or "Untitled",
                   "HumanWrite AI — side-by-side comparison report")
        doc.add_paragraph(
            "Left column shows the original paragraph; right column shows "
            "the revised paragraph. Paragraphs are aligned by position."
        )
        table = doc.add_table(rows=1, cols=2)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text = "Original"
        hdr[1].text = "Revised"
        orig_paras = split_paragraphs(original_text)
        new_paras = split_paragraphs(text)
        for i in range(max(len(orig_paras), len(new_paras))):
            row = table.add_row().cells
            row[0].text = orig_paras[i] if i < len(orig_paras) else ""
            row[1].text = new_paras[i] if i < len(new_paras) else ""
            for cell in row:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(10)
        table.columns[0].width = Inches(3.0)
        table.columns[1].width = Inches(3.0)
    else:
        label = "Original text" if kind == "original" else "Revised text"
        _add_title(doc, title or "Untitled",
                   f"HumanWrite AI — {label} (exported locally)")
        _add_body(doc, text)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def validate_docx(data: bytes) -> dict:
    """Check the bytes open as a real DOCX with content. Returns check dict."""
    from io import BytesIO
    from docx import Document as DocxDocument

    checks = []
    ok = True
    try:
        doc = DocxDocument(BytesIO(data))
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        tables = len(doc.tables)
        checks.append({"name": "opens_as_docx", "passed": True,
                       "detail": f"{len(paras)} paragraphs, {tables} tables"})
        has_text = bool(paras) or tables > 0
        checks.append({"name": "non_empty", "passed": has_text,
                       "detail": "document has content" if has_text else "empty"})
        ok = has_text
    except Exception as exc:  # noqa: BLE001 — validation must not raise
        checks.append({"name": "opens_as_docx", "passed": False,
                       "detail": str(exc)[:200]})
        ok = False
    return {"ok": ok, "checks": checks}
