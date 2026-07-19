import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_release import parse as fidelity_parse
from core.parsers.schwab_release import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_release_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_release_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_release_vest_date():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["vest_date"].confidence == "high"
    assert result["vest_date"].value == "2023-10-15"


def test_fidelity_release_shares_vested_gross():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["shares_vested_gross"].value == 100.0
    assert result["shares_vested_gross"].confidence == "high"


def test_fidelity_release_fmv():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["fmv_per_share_usd"].value == 785.50
    assert result["fmv_per_share_usd"].confidence == "high"


def test_fidelity_release_tax_withheld():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["shares_withheld_for_tax"].value == 30.0
    assert result["shares_withheld_for_tax"].confidence == "high"


def test_fidelity_release_missing_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("unrecognised")):
        result = fidelity_parse("dummy.pdf")
    assert all(f.confidence == "missing" for f in result.values())


def test_schwab_release_vest_date():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["vest_date"].value == "2024-04-10"
    assert result["vest_date"].confidence == "high"


def test_schwab_release_shares_vested_gross():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["shares_vested_gross"].value == 50.0


def test_schwab_release_fmv():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["fmv_per_share_usd"].value == 1285.75


def test_schwab_release_tax_withheld():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["shares_withheld_for_tax"].value == 15.0
