import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_statement import parse as fidelity_parse
from core.parsers.schwab_statement import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_statement_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_statement_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_statement_extracts_vesting_event():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert len(result["vesting_events"]) == 1
    v = result["vesting_events"][0]
    assert v["vest_date"] == "2023-10-15"
    assert v["shares_vested_gross"] == 100.0
    assert v["fmv_per_share_usd"] == 785.50
    assert v["shares_withheld_for_tax"] == 30.0


def test_fidelity_statement_extracts_sale_event():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert len(result["sale_events"]) == 1
    s = result["sale_events"][0]
    assert s["sale_date"] == "2023-11-20"
    assert s["shares_sold"] == 70.0
    assert s["price_per_share_usd"] == 810.25


def test_fidelity_statement_empty_text_returns_empty_lists():
    with patch("pdfplumber.open", return_value=_mock_pdf("nothing here")):
        result = fidelity_parse("dummy.pdf")
    assert result["vesting_events"] == []
    assert result["sale_events"] == []


def test_schwab_statement_extracts_vesting_event():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert len(result["vesting_events"]) == 1
    v = result["vesting_events"][0]
    assert v["vest_date"] == "2024-04-10"
    assert v["shares_vested_gross"] == 50.0
    assert v["fmv_per_share_usd"] == 1285.75
    assert v["shares_withheld_for_tax"] == 15.0


def test_schwab_statement_extracts_sale_event():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert len(result["sale_events"]) == 1
    s = result["sale_events"][0]
    assert s["sale_date"] == "2024-05-20"
    assert s["shares_sold"] == 35.0
    assert s["price_per_share_usd"] == 1350.0


def test_fidelity_statement_vesting_event_has_confidence():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    v = result["vesting_events"][0]
    assert "confidence" in v
    assert v["confidence"] == "high"


def test_schwab_statement_vesting_event_has_confidence():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    v = result["vesting_events"][0]
    assert "confidence" in v
    assert v["confidence"] == "high"


def test_fidelity_statement_sale_event_has_confidence():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    s = result["sale_events"][0]
    assert "confidence" in s
    assert s["confidence"] == "high"
