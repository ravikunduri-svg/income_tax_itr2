from datetime import date
from core.models import VestingEvent
from core.fx import FXRateTable
from core.cross_check import check_perquisite_mismatch


def test_no_mismatch_when_values_match():
    vest = VestingEvent(1, "2024-25", date(2022, 6, 1), 100.0, 50.0, 40.0)
    fx = FXRateTable({date(2022, 6, 1): 78.50})
    # 50 * 100 * 78.50 = 392500.0 exactly
    result = check_perquisite_mismatch(392_500.0, [vest], fx)
    assert result is None


def test_golden_case_6_mismatch_detected():
    vest = VestingEvent(1, "2024-25", date(2022, 6, 1), 100.0, 50.0, 40.0)
    fx = FXRateTable({date(2022, 6, 1): 78.50})
    # vesting sum = 392500.0, Form 16 reports 400000.0
    result = check_perquisite_mismatch(400_000.0, [vest], fx)
    assert result is not None
    assert result.form16_value_inr == 400_000.0
    assert result.vesting_sum_inr == 392_500.0
    assert result.difference_inr == 7_500.0
