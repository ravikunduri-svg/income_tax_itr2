import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_tax import parse as fidelity_parse
from core.parsers.schwab_tax import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_tax_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_tax_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_1042s_gross_income():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["gross_dividend_usd"].confidence == "high"
    assert result["gross_dividend_usd"].value == 1250.0


def test_fidelity_1042s_tax_withheld():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["us_tax_withheld_usd"].confidence == "high"
    assert result["us_tax_withheld_usd"].value == 375.0


def test_fidelity_tax_missing_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("nothing here")):
        result = fidelity_parse("dummy.pdf")
    assert all(f.confidence == "missing" for f in result.values())


def test_schwab_1099div_dividend():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["gross_dividend_usd"].confidence == "high"
    assert result["gross_dividend_usd"].value == 850.0


def test_schwab_1099div_tax_withheld():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["us_tax_withheld_usd"].confidence == "high"
    assert result["us_tax_withheld_usd"].value == 0.0
