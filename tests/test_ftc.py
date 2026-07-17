from datetime import date
from core.models import DividendEvent
from core.ftc import compute_ftc


def test_golden_case_7_dividend_and_ftc():
    dividends = [
        DividendEvent(1, "2024-25", date(2024, 3, 1), gross_dividend_usd=100.0, us_tax_withheld_usd=25.0),
        DividendEvent(2, "2024-25", date(2024, 6, 1), gross_dividend_usd=50.0, us_tax_withheld_usd=12.5),
    ]
    result = compute_ftc(dividends)
    assert result.total_us_tax_withheld_usd == 37.5
    assert "Form 67" in result.form_67_deadline_note
    assert "before" in result.form_67_deadline_note.lower()


def test_empty_dividend_list_gives_zero_credit():
    result = compute_ftc([])
    assert result.total_us_tax_withheld_usd == 0.0
