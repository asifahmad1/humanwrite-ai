"""Export validation tests for HumanWrite AI v1."""

from export_docx import export_docx, validate_docx
from export_pdf import export_pdf, validate_pdf
from export_txt import export_txt

SAMPLE = ("Artificial intelligence has changed education. "
          "Teachers have new ways to explain ideas.")


def test_txt_export():
    data = export_txt("My Doc", SAMPLE)
    assert data.decode("utf-8").startswith("My Doc")
    assert b"Teachers" in data


def test_docx_export_validates():
    data = export_docx("My Doc", SAMPLE, "revised")
    result = validate_docx(data)
    assert result["ok"] is True, result["checks"]


def test_docx_comparison_validates():
    data = export_docx("My Doc", SAMPLE, "comparison", original_text="Old text here.")
    result = validate_docx(data)
    assert result["ok"] is True, result["checks"]


def test_pdf_export_validates():
    data = export_pdf("My Doc", SAMPLE, "revised")
    result = validate_pdf(data)
    assert result["ok"] is True, result["checks"]


def test_pdf_comparison_validates():
    data = export_pdf("My Doc", SAMPLE, "comparison", original_text="Old text here.")
    result = validate_pdf(data)
    assert result["ok"] is True, result["checks"]
