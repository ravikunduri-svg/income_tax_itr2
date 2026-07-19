from datetime import date
import pytest
from core.schedule_fa import compute_schedule_fa


def test_computes_peak_and_closing_for_confirmed_calendar_year():
    values = {
        date(2024, 3, 31): 500_000.0,
        date(2024, 6, 30): 750_000.0,
        date(2024, 9, 30): 900_000.0,
        date(2024, 12, 31): 820_000.0,
    }
    result = compute_schedule_fa(2024, values)
    assert result.calendar_year == 2024
    assert result.peak_value_inr == 900_000.0
    assert result.closing_value_inr == 820_000.0


def test_golden_case_8_cross_calendar_year_isolation():
    # Values spanning two calendar years - only 2024 entries should be used
    # for calendar_year=2024, proving the FY window (which may span both
    # 2023 and 2024) never leaks into the FA calendar-year computation.
    values = {
        date(2023, 11, 30): 600_000.0,  # should be excluded
        date(2023, 12, 31): 610_000.0,  # should be excluded
        date(2024, 3, 31): 500_000.0,
        date(2024, 12, 31): 820_000.0,
    }
    result = compute_schedule_fa(2024, values)
    assert result.peak_value_inr == 820_000.0
    assert result.closing_value_inr == 820_000.0

    result_2023 = compute_schedule_fa(2023, values)
    assert result_2023.peak_value_inr == 610_000.0
    assert result_2023.closing_value_inr == 610_000.0


def test_raises_when_no_values_for_calendar_year():
    values = {date(2023, 12, 31): 610_000.0}
    with pytest.raises(ValueError, match="2024"):
        compute_schedule_fa(2024, values)


def test_raises_when_no_december_31_value():
    values = {date(2024, 6, 30): 750_000.0}
    with pytest.raises(ValueError, match="2024-12-31"):
        compute_schedule_fa(2024, values)
