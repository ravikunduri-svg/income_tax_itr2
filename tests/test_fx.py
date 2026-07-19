from datetime import date
import pytest
from core.fx import FXRateTable, MissingFXRateError


def test_get_rate_returns_value_for_known_date():
    table = FXRateTable({date(2024, 7, 15): 83.20})
    assert table.get_rate(date(2024, 7, 15)) == 83.20


def test_get_rate_raises_on_missing_date():
    table = FXRateTable({date(2024, 7, 15): 83.20})
    with pytest.raises(MissingFXRateError) as exc_info:
        table.get_rate(date(2024, 8, 1))
    assert date(2024, 8, 1) in exc_info.value.missing_dates


def test_check_dates_present_raises_listing_all_missing_dates():
    table = FXRateTable({date(2024, 7, 15): 83.20})
    with pytest.raises(MissingFXRateError) as exc_info:
        table.check_dates_present({date(2024, 7, 15), date(2024, 8, 1), date(2024, 9, 1)})
    assert exc_info.value.missing_dates == [date(2024, 8, 1), date(2024, 9, 1)]


def test_check_dates_present_passes_when_all_present():
    table = FXRateTable({date(2024, 7, 15): 83.20, date(2024, 8, 1): 83.50})
    table.check_dates_present({date(2024, 7, 15), date(2024, 8, 1)})
