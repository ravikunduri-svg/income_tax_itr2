from datetime import date
from core.models import (
    VestingEvent, SaleEvent, SaleLotAllocation, DividendEvent,
    Form16Summary, Form26ASSummary,
)


def test_vesting_event_fields():
    v = VestingEvent(
        id=1, assessment_year="2024-25", vest_date=date(2022, 6, 1),
        shares_vested_gross=100.0, fmv_per_share_usd=50.0,
        shares_withheld_for_tax=40.0,
    )
    assert v.vest_date == date(2022, 6, 1)
    assert v.shares_vested_gross == 100.0


def test_sale_event_and_lot_allocation_fields():
    s = SaleEvent(
        id=1, assessment_year="2024-25", sale_date=date(2024, 7, 15),
        quantity_sold=100.0, sale_price_per_share_usd=70.0,
    )
    alloc = SaleLotAllocation(sale_event_id=1, vesting_event_id=1, quantity_allocated=100.0)
    assert s.quantity_sold == 100.0
    assert alloc.quantity_allocated == 100.0


def test_dividend_event_fields():
    d = DividendEvent(
        id=1, assessment_year="2024-25", payment_date=date(2024, 3, 1),
        gross_dividend_usd=100.0, us_tax_withheld_usd=25.0,
    )
    assert d.gross_dividend_usd == 100.0


def test_form16_and_26as_summary_fields():
    f16 = Form16Summary(
        assessment_year="2024-25", gross_salary_inr=2_000_000.0,
        rsu_perquisite_value_inr=392_500.0, tds_inr=350_000.0,
    )
    f26as = Form26ASSummary(assessment_year="2024-25", total_tds_tcs_inr=350_000.0)
    assert f16.rsu_perquisite_value_inr == 392_500.0
    assert f26as.total_tds_tcs_inr == 350_000.0
