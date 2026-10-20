"""TXT export for HumanWrite AI v1."""

from __future__ import annotations

from nlp import split_paragraphs


def export_txt(title: str, text: str, kind: str = "revised") -> bytes:
    lines = [title or "Untitled", "=" * max(len(title or "Untitled"), 8), ""]
    if kind == "comparison":
        lines.append("(Comparison reports are available as DOCX or PDF.)")
        lines.append("")
    for para in split_paragraphs(text):
        lines.append(para)
        lines.append("")
    return "\n".join(lines).encode("utf-8")
