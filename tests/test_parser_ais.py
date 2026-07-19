import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.ais import parse

FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "ais_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_ais_extracts_tds():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "high"
    assert result["tds_inr"].value == 350000.0


def test_ais_missing_tds_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("no data here")):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "missing"
    assert result["tds_inr"].value is None
