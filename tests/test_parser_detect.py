from unittest.mock import MagicMock, patch

from core.parsers.detect import detect_document_type


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_detects_form16():
    text = "FORM NO. 16\nCertificate under section 203 of the Income-tax Act"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "form16"


def test_detects_ais():
    text = "Annual Information Statement\nAssessment Year: 2024-25"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "ais"


def test_detects_fidelity_release():
    text = "Fidelity Investments\nRSU Release Confirmation\nRelease Date: 10/15/2023"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_release"


def test_detects_fidelity_tax():
    text = "Fidelity Investments\nFORM 1042-S\nGross Income: 1250.00"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_tax"


def test_detects_fidelity_statement():
    text = "Fidelity Investments\nAccount Activity\nTransaction Type\nRSU VEST"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_statement"


def test_detects_schwab_release():
    text = "Charles Schwab\nStock Plan Release Confirmation\nRelease Date: 04/10/2024"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_release"


def test_detects_schwab_tax():
    text = "Charles Schwab\nForm 1099-DIV\nTotal ordinary dividends"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_tax"


def test_detects_schwab_statement():
    text = "Charles Schwab\nAccount Activity\nRS\nSell\nTax Wh"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_statement"


def test_unknown_document_returns_unknown():
    with patch("pdfplumber.open", return_value=_mock_pdf("random unrelated text")):
        assert detect_document_type("dummy.pdf") == "unknown"
