import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.form16 import parse

FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "form16_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_form16_extracts_gross_salary():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["gross_salary_inr"].confidence == "high"
    assert result["gross_salary_inr"].value == 3500000.0


def test_form16_extracts_perquisite():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["rsu_perquisite_value_inr"].confidence == "high"
    assert result["rsu_perquisite_value_inr"].value == 392500.0


def test_form16_extracts_tds():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "high"
    assert result["tds_inr"].value == 350000.0


def test_form16_missing_fields_return_missing_not_exception():
    with patch("pdfplumber.open", return_value=_mock_pdf("unrecognised content")):
        result = parse("dummy.pdf")
    assert result["gross_salary_inr"].confidence == "missing"
    assert result["gross_salary_inr"].value is None
    assert result["rsu_perquisite_value_inr"].confidence == "missing"
    assert result["tds_inr"].confidence == "missing"
