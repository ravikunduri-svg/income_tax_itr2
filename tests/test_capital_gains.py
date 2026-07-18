from datetime import date
import pytest
from core.models import VestingEvent, SaleEvent, SaleLotAllocation
from core.fx import FXRateTable
from core.capital_gains import add_months, is_long_term, is_near_24mo_boundary, compute_sale_gains


def test_add_months_simple():
    assert add_months(date(2022, 1, 15), 24) == date(2024, 1, 15)


def test_add_months_handles_day_overflow():
    # Jan 31 + 1 month -> Feb has no 31st, clamp to Feb 28 (2023 is not a leap year)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)


def test_is_long_term_exactly_24_months_is_not_long_term():
    assert is_long_term(date(2022, 3, 10), date(2024, 3, 10)) is False


def test_is_long_term_24_months_plus_one_day_is_long_term():
    assert is_long_term(date(2022, 3, 10), date(2024, 3, 11)) is True


def test_is_long_term_well_short_of_threshold():
    assert is_long_term(date(2024, 1, 10), date(2024, 8, 10)) is False


def test_is_near_24mo_boundary_true_within_window():
    assert is_near_24mo_boundary(date(2022, 3, 10), date(2024, 3, 12), days_window=5) is True


def test_is_near_24mo_boundary_false_outside_window():
    assert is_near_24mo_boundary(date(2022, 3, 10), date(2024, 6, 1), days_window=5) is False


def test_golden_case_1_standard_ltcg():
    vest = VestingEvent(1, "2024-25", date(2022, 6, 1), 100.0, 50.0, 40.0)
    sale = SaleEvent(1, "2024-25", date(2024, 7, 15), 100.0, 70.0)
    allocations = [SaleLotAllocation(sale_event_id=1, vesting_event_id=1, quantity_allocated=100.0)]
    fx = FXRateTable({date(2022, 6, 1): 78.50, date(2024, 7, 15): 83.20})

    results = compute_sale_gains(sale, allocations, {1: vest}, fx)

    assert len(results) == 1
    r = results[0]
    assert r.cost_basis_inr == pytest.approx(392_500.0)
    assert r.proceeds_inr == pytest.approx(582_400.0)
    assert r.gain_inr == pytest.approx(189_900.0)
    assert r.is_long_term is True


def test_golden_case_2_stcg():
    vest = VestingEvent(2, "2024-25", date(2024, 1, 10), 50.0, 40.0, 20.0)
    sale = SaleEvent(2, "2024-25", date(2024, 8, 10), 50.0, 45.0)
    allocations = [SaleLotAllocation(sale_event_id=2, vesting_event_id=2, quantity_allocated=50.0)]
    fx = FXRateTable({date(2024, 1, 10): 83.00, date(2024, 8, 10): 83.50})

    results = compute_sale_gains(sale, allocations, {2: vest}, fx)

    assert len(results) == 1
    r = results[0]
    assert r.cost_basis_inr == pytest.approx(166_000.0)
    assert r.proceeds_inr == pytest.approx(187_875.0)
    assert r.gain_inr == pytest.approx(21_875.0)
    assert r.is_long_term is False


def test_golden_case_3_boundary_exactly_24_months_is_stcg():
    vest = VestingEvent(3, "2024-25", date(2022, 3, 10), 10.0, 100.0, 4.0)
    sale = SaleEvent(3, "2024-25", date(2024, 3, 10), 10.0, 120.0)
    allocations = [SaleLotAllocation(sale_event_id=3, vesting_event_id=3, quantity_allocated=10.0)]
    fx = FXRateTable({date(2022, 3, 10): 80.00, date(2024, 3, 10): 85.00})

    results = compute_sale_gains(sale, allocations, {3: vest}, fx)

    assert len(results) == 1
    r = results[0]
    assert r.cost_basis_inr == pytest.approx(80_000.0)
    assert r.proceeds_inr == pytest.approx(102_000.0)
    assert r.gain_inr == pytest.approx(22_000.0)
    assert r.is_long_term is False


def test_golden_case_4_boundary_24_months_plus_1_day_is_ltcg():
    vest = VestingEvent(4, "2024-25", date(2022, 3, 10), 10.0, 100.0, 4.0)
    sale = SaleEvent(4, "2024-25", date(2024, 3, 11), 10.0, 120.0)
    allocations = [SaleLotAllocation(sale_event_id=4, vesting_event_id=4, quantity_allocated=10.0)]
    fx = FXRateTable({date(2022, 3, 10): 80.00, date(2024, 3, 11): 85.00})

    results = compute_sale_gains(sale, allocations, {4: vest}, fx)

    assert len(results) == 1
    r = results[0]
    assert r.gain_inr == pytest.approx(22_000.0)
    assert r.is_long_term is True


def test_golden_case_9_split_lot_sale_mixed_classification():
    vest_a = VestingEvent(10, "2024-25", date(2022, 1, 1), 100.0, 40.0, 40.0)
    vest_b = VestingEvent(11, "2024-25", date(2023, 6, 1), 50.0, 45.0, 20.0)
    sale = SaleEvent(9, "2024-25", date(2024, 8, 1), 150.0, 60.0)
    allocations = [
        SaleLotAllocation(sale_event_id=9, vesting_event_id=10, quantity_allocated=100.0),
        SaleLotAllocation(sale_event_id=9, vesting_event_id=11, quantity_allocated=50.0),
    ]
    fx = FXRateTable({
        date(2022, 1, 1): 75.00,
        date(2023, 6, 1): 81.00,
        date(2024, 8, 1): 83.75,
    })

    results = compute_sale_gains(sale, allocations, {10: vest_a, 11: vest_b}, fx)

    assert len(results) == 2
    lot_a = next(r for r in results if r.vesting_event_id == 10)
    lot_b = next(r for r in results if r.vesting_event_id == 11)

    assert lot_a.cost_basis_inr == pytest.approx(300_000.0)
    assert lot_a.proceeds_inr == pytest.approx(502_500.0)
    assert lot_a.gain_inr == pytest.approx(202_500.0)
    assert lot_a.is_long_term is True  # vested 2022-01-01, sold 2024-08-01: > 24 months

    assert lot_b.cost_basis_inr == pytest.approx(182_250.0)
    assert lot_b.proceeds_inr == pytest.approx(251_250.0)
    assert lot_b.gain_inr == pytest.approx(69_000.0)
    assert lot_b.is_long_term is False  # vested 2023-06-01, sold 2024-08-01: < 24 months


def test_golden_case_10_mismatched_lot_allocation_raises():
    vest = VestingEvent(12, "2024-25", date(2022, 1, 1), 200.0, 40.0, 80.0)
    sale = SaleEvent(10, "2024-25", date(2024, 8, 1), 200.0, 60.0)
    allocations = [SaleLotAllocation(sale_event_id=10, vesting_event_id=12, quantity_allocated=150.0)]
    fx = FXRateTable({date(2022, 1, 1): 75.00, date(2024, 8, 1): 83.75})

    with pytest.raises(ValueError, match="quantity_sold=200.0"):
        compute_sale_gains(sale, allocations, {12: vest}, fx)


def test_golden_case_5_missing_fx_rate_raises():
    from core.fx import MissingFXRateError
    vest = VestingEvent(13, "2024-25", date(2022, 6, 1), 100.0, 50.0, 40.0)
    sale = SaleEvent(11, "2024-25", date(2024, 7, 15), 100.0, 70.0)
    allocations = [SaleLotAllocation(sale_event_id=11, vesting_event_id=13, quantity_allocated=100.0)]
    fx = FXRateTable({date(2022, 6, 1): 78.50})  # missing the sale date rate

    with pytest.raises(MissingFXRateError) as exc_info:
        compute_sale_gains(sale, allocations, {13: vest}, fx)
    assert date(2024, 7, 15) in exc_info.value.missing_dates
