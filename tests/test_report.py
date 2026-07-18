from datetime import date
from core.models import VestingEvent, SaleEvent, SaleLotAllocation, DividendEvent, Form16Summary
from core.fx import FXRateTable
from core.report import build_report


def test_build_report_assembles_all_sections():
    vest = VestingEvent(1, "2024-25", date(2022, 6, 1), 100.0, 50.0, 40.0)
    sale = SaleEvent(1, "2024-25", date(2024, 7, 15), 100.0, 70.0)
    allocations = [SaleLotAllocation(sale_event_id=1, vesting_event_id=1, quantity_allocated=100.0)]
    dividends = [DividendEvent(1, "2024-25", date(2024, 3, 1), 100.0, 25.0)]
    form16 = Form16Summary("2024-25", gross_salary_inr=2_000_000.0, rsu_perquisite_value_inr=392_500.0, tds_inr=350_000.0)
    fx = FXRateTable({date(2022, 6, 1): 78.50, date(2024, 7, 15): 83.20, date(2024, 12, 31): 85.00})

    report = build_report(
        form16=form16,
        vesting_events=[vest],
        sale_events=[sale],
        allocations_by_sale={1: allocations},
        dividend_events=dividends,
        fx_table=fx,
        schedule_fa_calendar_year=2024,
        schedule_fa_monthly_values={date(2024, 12, 31): 900_000.0},
    )

    assert report.perquisite_mismatch is None
    assert len(report.lot_gains) == 1
    assert report.lot_gains[0].gain_inr == 189_900.0
    assert report.ftc.total_us_tax_withheld_usd == 25.0
    assert report.schedule_fa.closing_value_inr == 900_000.0
