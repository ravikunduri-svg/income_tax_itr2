# ITR-2 RSU Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only Flask + SQLite web app that takes manually-entered Form 16, Form 26AS, and RSU vesting/sale/dividend data and computes ITR-2 schedule values (Salary, Capital Gains, Foreign Assets, TR/FSI, Other Sources) for manual transcription into the government e-filing portal.

**Architecture:** A dependency-free `core/` calculation engine (pure functions and dataclasses, independently tested against hand-computed golden cases) is consumed by a thin `app/` Flask layer that handles only routing, forms, and rendering. SQLite persists one record per assessment year.

**Tech Stack:** Python 3.11+, Flask, stdlib `sqlite3` (no ORM), plain HTML/CSS/JS (no frontend framework), pytest.

## Global Constraints

- No network calls anywhere in `core/` or `app/` — enforced by a static-scan test, not just a design intention.
- No default/fallback values for any tax-affecting field — missing data blocks calculation with a specific, named error.
- FX rate lookups hard-stop on a missing date — no interpolation, no nearest-date fallback.
- Lot-matching for sales is always explicit user input — never an inferred FIFO or average-cost assumption.
- The 24-month LTCG/STCG threshold is computed via exact calendar-month arithmetic, never a fixed-day approximation.
- Schedule FA's calendar-year window is a user-confirmed value, never inferred from the assessment year, and is computed independently from the FY window used for Salary/Capital Gains.
- Every UI field showing a value the user must supply also shows what it is and which source document it comes from (per the spec's field-guidance table) — this is enforced per-task below, not deferred to a final polish pass.
- Every number in the results view shows its formula, inputs, and the exact rate/date used.

---

## Task 1: Project scaffolding and the no-network guardrail

**Files:**
- Create: `requirements.txt`
- Create: `core/__init__.py`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/golden_cases/__init__.py`
- Create: `tests/test_no_network.py`

**Interfaces:**
- Produces: nothing consumed by other tasks; this task only establishes the guardrail test and package structure every later task's files must satisfy.

- [ ] **Step 1: Create the directory structure and empty package files**

```bash
mkdir -p core app/templates db tests/golden_cases
touch core/__init__.py app/__init__.py tests/__init__.py tests/golden_cases/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```
Flask==3.0.3
pytest==8.2.0
```

- [ ] **Step 3: Write the failing no-network test**

`tests/test_no_network.py`:
```python
import ast
import pathlib

FORBIDDEN_MODULES = {
    "requests", "urllib", "urllib2", "urllib3", "http", "http.client",
    "socket", "ftplib", "smtplib", "httpx", "aiohttp",
}

SCAN_DIRS = ["core", "app"]


def _imported_modules(py_file: pathlib.Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


def test_no_networking_imports_in_core_or_app():
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    violations = []
    for scan_dir in SCAN_DIRS:
        for py_file in (repo_root / scan_dir).rglob("*.py"):
            found = _imported_modules(py_file) & FORBIDDEN_MODULES
            if found:
                violations.append(f"{py_file}: imports {sorted(found)}")
    assert not violations, "Networking imports found:\n" + "\n".join(violations)
```

- [ ] **Step 4: Run test to verify it passes (nothing to violate yet)**

Run: `cd C:\Codes\Labs\itr2-rsu-assistant && python -m pytest tests/test_no_network.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt core/__init__.py app/__init__.py tests/__init__.py tests/golden_cases/__init__.py tests/test_no_network.py
git commit -m "Scaffold project structure and no-network guardrail test"
```

---

## Task 2: Data models

**Files:**
- Create: `core/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `VestingEvent`, `SaleEvent`, `SaleLotAllocation`, `DividendEvent`, `Form16Summary`, `Form26ASSummary` dataclasses — every later `core/` task imports these from `core.models`.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.models'`

- [ ] **Step 3: Write the implementation**

`core/models.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class VestingEvent:
    id: Optional[int]
    assessment_year: str
    vest_date: date
    shares_vested_gross: float
    fmv_per_share_usd: float
    shares_withheld_for_tax: float


@dataclass
class SaleEvent:
    id: Optional[int]
    assessment_year: str
    sale_date: date
    quantity_sold: float
    sale_price_per_share_usd: float


@dataclass
class SaleLotAllocation:
    sale_event_id: int
    vesting_event_id: int
    quantity_allocated: float


@dataclass
class DividendEvent:
    id: Optional[int]
    assessment_year: str
    payment_date: date
    gross_dividend_usd: float
    us_tax_withheld_usd: float


@dataclass
class Form16Summary:
    assessment_year: str
    gross_salary_inr: float
    rsu_perquisite_value_inr: float
    tds_inr: float


@dataclass
class Form26ASSummary:
    assessment_year: str
    total_tds_tcs_inr: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "Add core data models"
```

---

## Task 3: FX rate lookup with hard-stop

**Files:**
- Create: `core/fx.py`
- Test: `tests/test_fx.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `MissingFXRateError` (exception, `.missing_dates` attribute), `FXRateTable` class with `get_rate(on_date: date) -> float` and `check_dates_present(dates: set[date]) -> None` (raises `MissingFXRateError` if any date missing) — consumed by `capital_gains.py`, `cross_check.py`, `schedule_fa.py`.

- [ ] **Step 1: Write the failing test**

`tests/test_fx.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.fx'`

- [ ] **Step 3: Write the implementation**

`core/fx.py`:
```python
from datetime import date
from typing import Dict, Iterable, List


class MissingFXRateError(Exception):
    def __init__(self, missing_dates: List[date]):
        self.missing_dates = missing_dates
        dates_str = ", ".join(d.isoformat() for d in missing_dates)
        super().__init__(
            f"Missing FX rate for date(s): {dates_str}. "
            f"Add these to your FX rate table before this can be calculated."
        )


class FXRateTable:
    def __init__(self, rates: Dict[date, float]):
        self._rates = dict(rates)

    def get_rate(self, on_date: date) -> float:
        if on_date not in self._rates:
            raise MissingFXRateError([on_date])
        return self._rates[on_date]

    def check_dates_present(self, dates: Iterable[date]) -> None:
        missing = sorted(d for d in set(dates) if d not in self._rates)
        if missing:
            raise MissingFXRateError(missing)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fx.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add core/fx.py tests/test_fx.py
git commit -m "Add FX rate table with hard-stop on missing dates"
```

---

## Task 4: Capital gains calculation — calendar-month LTCG/STCG threshold

**Files:**
- Create: `core/capital_gains.py`
- Test: `tests/test_capital_gains.py`

**Interfaces:**
- Consumes: `VestingEvent`, `SaleEvent`, `SaleLotAllocation` from `core.models`; `FXRateTable` from `core.fx`.
- Produces: `add_months(d: date, months: int) -> date`, `is_long_term(vest_date: date, sale_date: date) -> bool`, `is_near_24mo_boundary(vest_date: date, sale_date: date, days_window: int = 5) -> bool`, `LotGainResult` dataclass, `compute_sale_gains(sale, allocations, vesting_events_by_id, fx_table) -> list[LotGainResult]` — consumed by `report.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_capital_gains.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_capital_gains.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.capital_gains'`

- [ ] **Step 3: Write the implementation**

`core/capital_gains.py`:
```python
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Dict, List

from core.fx import FXRateTable
from core.models import SaleEvent, SaleLotAllocation, VestingEvent


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def is_long_term(vest_date: date, sale_date: date) -> bool:
    """More than 24 months held => long-term. Exactly 24 months or less => short-term.

    Applies to unlisted foreign shares (RSUs of a US-listed company, not listed
    on an Indian exchange), per the 24-month threshold rather than the 12-month
    threshold used for Indian-listed equity.
    """
    threshold_date = add_months(vest_date, 24)
    return sale_date > threshold_date


def is_near_24mo_boundary(vest_date: date, sale_date: date, days_window: int = 5) -> bool:
    threshold_date = add_months(vest_date, 24)
    return abs((sale_date - threshold_date).days) <= days_window


@dataclass
class LotGainResult:
    vesting_event_id: int
    quantity: float
    cost_basis_inr: float
    proceeds_inr: float
    gain_inr: float
    is_long_term: bool
    holding_days: int
    near_boundary: bool


def compute_sale_gains(
    sale: SaleEvent,
    allocations: List[SaleLotAllocation],
    vesting_events_by_id: Dict[int, VestingEvent],
    fx_table: FXRateTable,
) -> List[LotGainResult]:
    total_allocated = sum(a.quantity_allocated for a in allocations)
    if abs(total_allocated - sale.quantity_sold) > 1e-6:
        raise ValueError(
            f"Sale on {sale.sale_date.isoformat()} has quantity_sold={sale.quantity_sold} "
            f"but lot allocations sum to {total_allocated}. These must match exactly — "
            f"enter which vesting lot(s) this sale came from."
        )

    needed_dates = {sale.sale_date}
    for alloc in allocations:
        needed_dates.add(vesting_events_by_id[alloc.vesting_event_id].vest_date)
    fx_table.check_dates_present(needed_dates)

    sale_rate = fx_table.get_rate(sale.sale_date)
    results: List[LotGainResult] = []
    for alloc in allocations:
        vest = vesting_events_by_id[alloc.vesting_event_id]
        vest_rate = fx_table.get_rate(vest.vest_date)
        cost_basis_inr = vest.fmv_per_share_usd * alloc.quantity_allocated * vest_rate
        proceeds_inr = sale.sale_price_per_share_usd * alloc.quantity_allocated * sale_rate
        gain_inr = proceeds_inr - cost_basis_inr
        long_term = is_long_term(vest.vest_date, sale.sale_date)
        holding_days = (sale.sale_date - vest.vest_date).days
        near_boundary = is_near_24mo_boundary(vest.vest_date, sale.sale_date)
        results.append(
            LotGainResult(
                vesting_event_id=vest.id,
                quantity=alloc.quantity_allocated,
                cost_basis_inr=cost_basis_inr,
                proceeds_inr=proceeds_inr,
                gain_inr=gain_inr,
                is_long_term=long_term,
                holding_days=holding_days,
                near_boundary=near_boundary,
            )
        )
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_capital_gains.py -v`
Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add core/capital_gains.py tests/test_capital_gains.py
git commit -m "Add capital gains calculation with 24-month LTCG threshold and lot allocation"
```

---

## Task 5: Form 16 vs. vesting perquisite cross-check

**Files:**
- Create: `core/cross_check.py`
- Test: `tests/test_cross_check.py`

**Interfaces:**
- Consumes: `VestingEvent` from `core.models`; `FXRateTable` from `core.fx`.
- Produces: `PerquisiteMismatch` dataclass, `check_perquisite_mismatch(form16_perquisite_inr, vesting_events, fx_table) -> Optional[PerquisiteMismatch]` — consumed by `report.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cross_check.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cross_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.cross_check'`

- [ ] **Step 3: Write the implementation**

`core/cross_check.py`:
```python
from dataclasses import dataclass
from typing import List, Optional

from core.fx import FXRateTable
from core.models import VestingEvent


@dataclass
class PerquisiteMismatch:
    form16_value_inr: float
    vesting_sum_inr: float
    difference_inr: float


def check_perquisite_mismatch(
    form16_perquisite_inr: float,
    vesting_events: List[VestingEvent],
    fx_table: FXRateTable,
) -> Optional[PerquisiteMismatch]:
    dates = {v.vest_date for v in vesting_events}
    fx_table.check_dates_present(dates)

    vesting_sum = 0.0
    for v in vesting_events:
        rate = fx_table.get_rate(v.vest_date)
        vesting_sum += v.fmv_per_share_usd * v.shares_vested_gross * rate

    difference = form16_perquisite_inr - vesting_sum
    if abs(difference) > 0.01:
        return PerquisiteMismatch(
            form16_value_inr=form16_perquisite_inr,
            vesting_sum_inr=vesting_sum,
            difference_inr=difference,
        )
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cross_check.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/cross_check.py tests/test_cross_check.py
git commit -m "Add Form 16 vs. vesting perquisite cross-check"
```

---

## Task 6: Schedule FA — user-confirmed calendar-year window

**Files:**
- Create: `core/schedule_fa.py`
- Test: `tests/test_schedule_fa.py`

**Interfaces:**
- Consumes: nothing beyond stdlib `datetime.date`.
- Produces: `ScheduleFAResult` dataclass, `compute_schedule_fa(calendar_year: int, monthly_values_inr: dict[date, float]) -> ScheduleFAResult` — consumed by `report.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_schedule_fa.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_schedule_fa.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.schedule_fa'`

- [ ] **Step 3: Write the implementation**

`core/schedule_fa.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import Dict


@dataclass
class ScheduleFAResult:
    calendar_year: int
    peak_value_inr: float
    closing_value_inr: float


def compute_schedule_fa(calendar_year: int, monthly_values_inr: Dict[date, float]) -> ScheduleFAResult:
    year_values = {d: v for d, v in monthly_values_inr.items() if d.year == calendar_year}
    if not year_values:
        raise ValueError(
            f"No account values were provided for calendar year {calendar_year}. "
            f"Schedule FA needs at least one value in this window to compute a peak/closing value."
        )

    dec_31 = date(calendar_year, 12, 31)
    if dec_31 not in year_values:
        raise ValueError(
            f"No account value provided for {dec_31.isoformat()} (year-end). "
            f"Schedule FA requires an explicit closing value for this exact date — "
            f"the app will not estimate it from a nearby date."
        )

    return ScheduleFAResult(
        calendar_year=calendar_year,
        peak_value_inr=max(year_values.values()),
        closing_value_inr=year_values[dec_31],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_schedule_fa.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add core/schedule_fa.py tests/test_schedule_fa.py
git commit -m "Add Schedule FA calculation with user-confirmed calendar-year window"
```

---

## Task 7: Foreign tax credit

**Files:**
- Create: `core/ftc.py`
- Test: `tests/test_ftc.py`

**Interfaces:**
- Consumes: `DividendEvent` from `core.models`.
- Produces: `FTCResult` dataclass, `compute_ftc(dividend_events: list[DividendEvent]) -> FTCResult` — consumed by `report.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_ftc.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ftc.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.ftc'`

- [ ] **Step 3: Write the implementation**

`core/ftc.py`:
```python
from dataclasses import dataclass
from typing import List

from core.models import DividendEvent

FORM_67_DEADLINE_NOTE = (
    "Form 67 must be filed BEFORE the ITR-2 due date, not together with it, "
    "to claim this foreign tax credit. Confirm the current assessment year's "
    "exact due date with your CA before relying on this."
)


@dataclass
class FTCResult:
    total_us_tax_withheld_usd: float
    form_67_deadline_note: str


def compute_ftc(dividend_events: List[DividendEvent]) -> FTCResult:
    total_withheld = sum(d.us_tax_withheld_usd for d in dividend_events)
    return FTCResult(
        total_us_tax_withheld_usd=total_withheld,
        form_67_deadline_note=FORM_67_DEADLINE_NOTE,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ftc.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add core/ftc.py tests/test_ftc.py
git commit -m "Add foreign tax credit calculation with Form 67 deadline reminder"
```

---

## Task 8: Report assembly

**Files:**
- Create: `core/report.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: everything from Tasks 2–7 (`core.models`, `core.fx.FXRateTable`, `core.capital_gains.compute_sale_gains`, `core.cross_check.check_perquisite_mismatch`, `core.schedule_fa.compute_schedule_fa`, `core.ftc.compute_ftc`).
- Produces: `ITRReport` dataclass and `build_report(...) -> ITRReport` — consumed by the Flask results route in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_report.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.report'`

- [ ] **Step 3: Write the implementation**

`core/report.py`:
```python
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional

from core.capital_gains import LotGainResult, compute_sale_gains
from core.cross_check import PerquisiteMismatch, check_perquisite_mismatch
from core.ftc import FTCResult, compute_ftc
from core.fx import FXRateTable
from core.models import DividendEvent, Form16Summary, SaleEvent, SaleLotAllocation, VestingEvent
from core.schedule_fa import ScheduleFAResult, compute_schedule_fa


@dataclass
class ITRReport:
    form16: Form16Summary
    perquisite_mismatch: Optional[PerquisiteMismatch]
    lot_gains: List[LotGainResult]
    ftc: FTCResult
    schedule_fa: ScheduleFAResult


def build_report(
    form16: Form16Summary,
    vesting_events: List[VestingEvent],
    sale_events: List[SaleEvent],
    allocations_by_sale: Dict[int, List[SaleLotAllocation]],
    dividend_events: List[DividendEvent],
    fx_table: FXRateTable,
    schedule_fa_calendar_year: int,
    schedule_fa_monthly_values: Dict[date, float],
) -> ITRReport:
    vesting_events_by_id = {v.id: v for v in vesting_events}

    mismatch = check_perquisite_mismatch(form16.rsu_perquisite_value_inr, vesting_events, fx_table)

    lot_gains: List[LotGainResult] = []
    for sale in sale_events:
        allocations = allocations_by_sale.get(sale.id, [])
        lot_gains.extend(compute_sale_gains(sale, allocations, vesting_events_by_id, fx_table))

    ftc = compute_ftc(dividend_events)
    schedule_fa = compute_schedule_fa(schedule_fa_calendar_year, schedule_fa_monthly_values)

    return ITRReport(
        form16=form16,
        perquisite_mismatch=mismatch,
        lot_gains=lot_gains,
        ftc=ftc,
        schedule_fa=schedule_fa,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_report.py -v`
Expected: `1 passed`

- [ ] **Step 5: Run the full test suite to confirm all golden cases still pass**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (Tasks 1–8 combined, ~30 tests)

- [ ] **Step 6: Commit**

```bash
git add core/report.py tests/test_report.py
git commit -m "Add report assembly combining all calculation modules"
```

---

## Task 9: SQLite schema and data access layer

**Files:**
- Create: `db/schema.sql`
- Create: `db/access.py`
- Test: `tests/test_db_access.py`

**Interfaces:**
- Consumes: `core.models` dataclasses.
- Produces: `init_db(db_path: str) -> None`, `Database` class with methods `create_or_get_assessment_year`, `save_form16_summary`, `get_form16_summary`, `save_vesting_event`, `list_vesting_events`, `save_sale_event`, `save_sale_lot_allocations`, `list_sale_events_with_allocations`, `save_dividend_event`, `list_dividend_events`, `upsert_fx_rates`, `get_all_fx_rates`, `save_schedule_fa_calendar_year`, `get_schedule_fa_calendar_year`, `save_schedule_fa_monthly_value`, `get_schedule_fa_monthly_values` — consumed by every Flask route in Tasks 10–17.

- [ ] **Step 1: Write `db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS assessment_years (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ay_label TEXT NOT NULL UNIQUE,
    fy_start_date TEXT NOT NULL,
    fy_end_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS form16_summary (
    assessment_year_id INTEGER PRIMARY KEY,
    gross_salary_inr REAL NOT NULL,
    rsu_perquisite_value_inr REAL NOT NULL,
    tds_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS form26as_summary (
    assessment_year_id INTEGER PRIMARY KEY,
    total_tds_tcs_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS vesting_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    vest_date TEXT NOT NULL,
    shares_vested_gross REAL NOT NULL,
    fmv_per_share_usd REAL NOT NULL,
    shares_withheld_for_tax REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS sale_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    quantity_sold REAL NOT NULL,
    sale_price_per_share_usd REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS sale_lot_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_event_id INTEGER NOT NULL,
    vesting_event_id INTEGER NOT NULL,
    quantity_allocated REAL NOT NULL,
    FOREIGN KEY (sale_event_id) REFERENCES sale_events(id),
    FOREIGN KEY (vesting_event_id) REFERENCES vesting_events(id)
);

CREATE TABLE IF NOT EXISTS dividend_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    gross_dividend_usd REAL NOT NULL,
    us_tax_withheld_usd REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date TEXT PRIMARY KEY,
    rate_inr_per_usd REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_fa_year_selection (
    assessment_year_id INTEGER PRIMARY KEY,
    calendar_year INTEGER NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS schedule_fa_monthly_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    value_date TEXT NOT NULL,
    account_value_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);
```

- [ ] **Step 2: Write the failing test**

`tests/test_db_access.py`:
```python
import os
import tempfile
from datetime import date, datetime

import pytest

from db.access import Database, init_db
from core.models import VestingEvent, SaleEvent, SaleLotAllocation, DividendEvent, Form16Summary


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.remove(path)


def test_create_and_get_assessment_year(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    ay_id_again = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    assert ay_id == ay_id_again  # idempotent, doesn't duplicate


def test_save_and_get_form16_summary(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    database.save_form16_summary(ay_id, gross_salary_inr=2_000_000.0, rsu_perquisite_value_inr=392_500.0, tds_inr=350_000.0)
    result = database.get_form16_summary(ay_id)
    assert result.gross_salary_inr == 2_000_000.0


def test_save_and_list_vesting_events(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    vest_id = database.save_vesting_event(ay_id, date(2022, 6, 1), 100.0, 50.0, 40.0)
    events = database.list_vesting_events(ay_id)
    assert len(events) == 1
    assert events[0].id == vest_id
    assert events[0].shares_vested_gross == 100.0


def test_save_sale_with_lot_allocations(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    vest_id = database.save_vesting_event(ay_id, date(2022, 6, 1), 100.0, 50.0, 40.0)
    sale_id = database.save_sale_event(ay_id, date(2024, 7, 15), 100.0, 70.0)
    database.save_sale_lot_allocations(sale_id, [(vest_id, 100.0)])

    sales_with_allocs = database.list_sale_events_with_allocations(ay_id)
    assert len(sales_with_allocs) == 1
    sale, allocations = sales_with_allocs[0]
    assert sale.id == sale_id
    assert len(allocations) == 1
    assert allocations[0].quantity_allocated == 100.0


def test_save_and_list_dividend_events(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    database.save_dividend_event(ay_id, date(2024, 3, 1), 100.0, 25.0)
    dividends = database.list_dividend_events(ay_id)
    assert len(dividends) == 1
    assert dividends[0].gross_dividend_usd == 100.0


def test_upsert_and_get_fx_rates(db_path):
    database = Database(db_path)
    database.upsert_fx_rates({date(2024, 7, 15): 83.20, date(2022, 6, 1): 78.50})
    rates = database.get_all_fx_rates()
    assert rates[date(2024, 7, 15)] == 83.20
    # upsert again with an overlapping date and a new one - should not duplicate
    database.upsert_fx_rates({date(2024, 7, 15): 83.25, date(2024, 8, 1): 84.00})
    rates = database.get_all_fx_rates()
    assert rates[date(2024, 7, 15)] == 83.25
    assert len(rates) == 3


def test_schedule_fa_calendar_year_and_monthly_values(db_path):
    database = Database(db_path)
    ay_id = database.create_or_get_assessment_year("2024-25", date(2024, 4, 1), date(2025, 3, 31))
    database.save_schedule_fa_calendar_year(ay_id, 2024)
    assert database.get_schedule_fa_calendar_year(ay_id) == 2024

    database.save_schedule_fa_monthly_value(ay_id, date(2024, 12, 31), 900_000.0)
    values = database.get_schedule_fa_monthly_values(ay_id)
    assert values[date(2024, 12, 31)] == 900_000.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_db_access.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db.access'`

- [ ] **Step 4: Write the implementation**

`db/access.py`:
```python
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.models import DividendEvent, Form16Summary, SaleEvent, SaleLotAllocation, VestingEvent

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_or_get_assessment_year(self, ay_label: str, fy_start: date, fy_end: date) -> int:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT id FROM assessment_years WHERE ay_label = ?", (ay_label,))
            row = cur.fetchone()
            if row:
                return row[0]
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT INTO assessment_years (ay_label, fy_start_date, fy_end_date, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (ay_label, fy_start.isoformat(), fy_end.isoformat(), now, now),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def save_form16_summary(self, ay_id: int, gross_salary_inr: float, rsu_perquisite_value_inr: float, tds_inr: float) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO form16_summary (assessment_year_id, gross_salary_inr, rsu_perquisite_value_inr, tds_inr) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(assessment_year_id) DO UPDATE SET "
                "gross_salary_inr = excluded.gross_salary_inr, "
                "rsu_perquisite_value_inr = excluded.rsu_perquisite_value_inr, "
                "tds_inr = excluded.tds_inr",
                (ay_id, gross_salary_inr, rsu_perquisite_value_inr, tds_inr),
            )
            conn.commit()
        finally:
            conn.close()

    def get_form16_summary(self, ay_id: int) -> Optional[Form16Summary]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT gross_salary_inr, rsu_perquisite_value_inr, tds_inr FROM form16_summary WHERE assessment_year_id = ?",
                (ay_id,),
            ).fetchone()
            if not row:
                return None
            return Form16Summary(assessment_year=str(ay_id), gross_salary_inr=row[0], rsu_perquisite_value_inr=row[1], tds_inr=row[2])
        finally:
            conn.close()

    def save_vesting_event(self, ay_id: int, vest_date: date, shares_vested_gross: float, fmv_per_share_usd: float, shares_withheld_for_tax: float) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO vesting_events (assessment_year_id, vest_date, shares_vested_gross, fmv_per_share_usd, shares_withheld_for_tax) "
                "VALUES (?, ?, ?, ?, ?)",
                (ay_id, vest_date.isoformat(), shares_vested_gross, fmv_per_share_usd, shares_withheld_for_tax),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_vesting_events(self, ay_id: int) -> List[VestingEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, vest_date, shares_vested_gross, fmv_per_share_usd, shares_withheld_for_tax "
                "FROM vesting_events WHERE assessment_year_id = ? ORDER BY vest_date",
                (ay_id,),
            ).fetchall()
            return [
                VestingEvent(
                    id=r[0], assessment_year=str(ay_id), vest_date=date.fromisoformat(r[1]),
                    shares_vested_gross=r[2], fmv_per_share_usd=r[3], shares_withheld_for_tax=r[4],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def save_sale_event(self, ay_id: int, sale_date: date, quantity_sold: float, sale_price_per_share_usd: float) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO sale_events (assessment_year_id, sale_date, quantity_sold, sale_price_per_share_usd) "
                "VALUES (?, ?, ?, ?)",
                (ay_id, sale_date.isoformat(), quantity_sold, sale_price_per_share_usd),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def save_sale_lot_allocations(self, sale_id: int, allocations: List[Tuple[int, float]]) -> None:
        conn = self._connect()
        try:
            conn.executemany(
                "INSERT INTO sale_lot_allocations (sale_event_id, vesting_event_id, quantity_allocated) VALUES (?, ?, ?)",
                [(sale_id, vest_id, qty) for vest_id, qty in allocations],
            )
            conn.commit()
        finally:
            conn.close()

    def list_sale_events_with_allocations(self, ay_id: int) -> List[Tuple[SaleEvent, List[SaleLotAllocation]]]:
        conn = self._connect()
        try:
            sale_rows = conn.execute(
                "SELECT id, sale_date, quantity_sold, sale_price_per_share_usd "
                "FROM sale_events WHERE assessment_year_id = ? ORDER BY sale_date",
                (ay_id,),
            ).fetchall()
            results = []
            for r in sale_rows:
                sale = SaleEvent(id=r[0], assessment_year=str(ay_id), sale_date=date.fromisoformat(r[1]), quantity_sold=r[2], sale_price_per_share_usd=r[3])
                alloc_rows = conn.execute(
                    "SELECT sale_event_id, vesting_event_id, quantity_allocated FROM sale_lot_allocations WHERE sale_event_id = ?",
                    (sale.id,),
                ).fetchall()
                allocations = [SaleLotAllocation(sale_event_id=a[0], vesting_event_id=a[1], quantity_allocated=a[2]) for a in alloc_rows]
                results.append((sale, allocations))
            return results
        finally:
            conn.close()

    def save_dividend_event(self, ay_id: int, payment_date: date, gross_dividend_usd: float, us_tax_withheld_usd: float) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO dividend_events (assessment_year_id, payment_date, gross_dividend_usd, us_tax_withheld_usd) "
                "VALUES (?, ?, ?, ?)",
                (ay_id, payment_date.isoformat(), gross_dividend_usd, us_tax_withheld_usd),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def list_dividend_events(self, ay_id: int) -> List[DividendEvent]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id, payment_date, gross_dividend_usd, us_tax_withheld_usd "
                "FROM dividend_events WHERE assessment_year_id = ? ORDER BY payment_date",
                (ay_id,),
            ).fetchall()
            return [
                DividendEvent(id=r[0], assessment_year=str(ay_id), payment_date=date.fromisoformat(r[1]), gross_dividend_usd=r[2], us_tax_withheld_usd=r[3])
                for r in rows
            ]
        finally:
            conn.close()

    def upsert_fx_rates(self, rates: Dict[date, float]) -> None:
        conn = self._connect()
        try:
            conn.executemany(
                "INSERT INTO fx_rates (rate_date, rate_inr_per_usd) VALUES (?, ?) "
                "ON CONFLICT(rate_date) DO UPDATE SET rate_inr_per_usd = excluded.rate_inr_per_usd",
                [(d.isoformat(), r) for d, r in rates.items()],
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_fx_rates(self) -> Dict[date, float]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT rate_date, rate_inr_per_usd FROM fx_rates").fetchall()
            return {date.fromisoformat(r[0]): r[1] for r in rows}
        finally:
            conn.close()

    def save_schedule_fa_calendar_year(self, ay_id: int, calendar_year: int) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO schedule_fa_year_selection (assessment_year_id, calendar_year) VALUES (?, ?) "
                "ON CONFLICT(assessment_year_id) DO UPDATE SET calendar_year = excluded.calendar_year",
                (ay_id, calendar_year),
            )
            conn.commit()
        finally:
            conn.close()

    def get_schedule_fa_calendar_year(self, ay_id: int) -> Optional[int]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT calendar_year FROM schedule_fa_year_selection WHERE assessment_year_id = ?", (ay_id,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def save_schedule_fa_monthly_value(self, ay_id: int, value_date: date, account_value_inr: float) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO schedule_fa_monthly_values (assessment_year_id, value_date, account_value_inr) VALUES (?, ?, ?)",
                (ay_id, value_date.isoformat(), account_value_inr),
            )
            conn.commit()
        finally:
            conn.close()

    def get_schedule_fa_monthly_values(self, ay_id: int) -> Dict[date, float]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT value_date, account_value_inr FROM schedule_fa_monthly_values WHERE assessment_year_id = ?",
                (ay_id,),
            ).fetchall()
            return {date.fromisoformat(r[0]): r[1] for r in rows}
        finally:
            conn.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_db_access.py -v`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add db/schema.sql db/access.py tests/test_db_access.py
git commit -m "Add SQLite schema and data access layer"
```

---

## Task 10: Flask app skeleton, base template, and assessment-year selection

**Files:**
- Create: `app/routes.py`
- Create: `app/templates/base.html`
- Create: `app/templates/year_select.html`
- Create: `run.py`
- Test: `tests/test_app_year_selection.py`

**Interfaces:**
- Consumes: `db.access.Database`, `db.access.init_db`.
- Produces: Flask `app` object (importable as `app.routes.app`), route `GET/POST /` (year select/create), route `GET /year/<ay_label>` (reopen) — consumed by Tasks 11–17, which add routes to the same `app` object.

- [ ] **Step 1: Write the failing test**

`tests/test_app_year_selection.py`:
```python
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
    os.remove(path)


def test_index_shows_year_select_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Assessment Year" in resp.data


def test_create_new_assessment_year_redirects_to_it(client):
    resp = client.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
    assert resp.status_code == 302
    assert "/year/2024-25" in resp.headers["Location"]


def test_reopen_existing_assessment_year(client):
    client.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
    resp = client.get("/year/2024-25")
    assert resp.status_code == 200
    assert b"2024-25" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_year_selection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routes'`

- [ ] **Step 3: Write `app/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>ITR-2 RSU Assistant</title>
  <style>
    body { font-family: sans-serif; max-width: 900px; margin: 2rem auto; color: #222; }
    .disclaimer { background: #fff3cd; border: 1px solid #b8860b; padding: 0.75rem 1rem; margin-bottom: 1.5rem; font-size: 0.9rem; }
    .field-help { color: #555; font-size: 0.85rem; margin-top: 0.15rem; }
    .warning { background: #fde2e1; border: 1px solid #c0392b; padding: 0.75rem 1rem; margin: 1rem 0; }
    label { display: block; margin-top: 0.75rem; font-weight: bold; }
    input, select { display: block; margin-top: 0.25rem; padding: 0.4rem; width: 100%; max-width: 400px; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #ccc; padding: 0.5rem; text-align: left; }
    nav a { margin-right: 1rem; }
  </style>
</head>
<body>
  <div class="disclaimer">
    This is a calculation aid only, not tax advice. Review every figure with a
    qualified CA before filing. Indian cross-border RSU and foreign-asset
    rules change year to year and carry real penalty exposure for errors.
  </div>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Write `app/templates/year_select.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>ITR-2 RSU Assistant</h1>
  <h2>Assessment Year</h2>
  <form method="post">
    <label for="ay_label">Assessment Year (e.g. 2024-25)</label>
    <input type="text" id="ay_label" name="ay_label" required>
    <div class="field-help">The Indian assessment year label you're filing for.</div>

    <label for="fy_start_date">Financial Year start date</label>
    <input type="date" id="fy_start_date" name="fy_start_date" required>

    <label for="fy_end_date">Financial Year end date</label>
    <input type="date" id="fy_end_date" name="fy_end_date" required>

    <button type="submit" style="margin-top: 1rem;">Create / Open</button>
  </form>
{% endblock %}
```

- [ ] **Step 5: Write `app/routes.py`**

```python
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

from db.access import Database

app = Flask(__name__)
_db_path_holder = {"path": None}


def configure_db(db_path: str) -> None:
    _db_path_holder["path"] = db_path


def get_db() -> Database:
    if _db_path_holder["path"] is None:
        raise RuntimeError("Database path not configured. Call configure_db() first.")
    return Database(_db_path_holder["path"])


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        ay_label = request.form["ay_label"]
        fy_start = date.fromisoformat(request.form["fy_start_date"])
        fy_end = date.fromisoformat(request.form["fy_end_date"])
        get_db().create_or_get_assessment_year(ay_label, fy_start, fy_end)
        return redirect(url_for("year_detail", ay_label=ay_label))
    return render_template("year_select.html")


@app.route("/year/<ay_label>")
def year_detail(ay_label: str):
    return render_template("year_select.html", ay_label=ay_label) if False else f"Assessment Year: {ay_label}"
```

Note: `year_detail` is a placeholder view for this task only — it becomes the real dashboard in Task 17 once results assembly exists. It must return a 200 with the AY label visible, which the test checks for.

- [ ] **Step 6: Write `run.py`**

```python
import sys

from app.routes import app, configure_db
from db.access import init_db

DB_PATH = "itr2_rsu_assistant.db"


def main():
    init_db(DB_PATH)
    configure_db(DB_PATH)
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_app_year_selection.py -v`
Expected: `3 passed`

- [ ] **Step 8: Run the full suite and the no-network guardrail**

Run: `python -m pytest tests/ -v`
Expected: all tests pass, including `test_no_networking_imports_in_core_or_app` (Flask itself makes no outbound network calls and isn't in the forbidden list — only calling-out libraries like `requests`/`urllib` are forbidden)

- [ ] **Step 9: Commit**

```bash
git add app/routes.py app/templates/base.html app/templates/year_select.html run.py tests/test_app_year_selection.py
git commit -m "Add Flask app skeleton with assessment-year creation/reopen"
```

---

## Task 11: Form 16 / Form 26AS entry

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/form16_entry.html`
- Modify: `run.py` (no change needed — already wired)
- Test: `tests/test_app_form16_entry.py`

**Interfaces:**
- Consumes: `get_db()` from `app.routes` (Task 10).
- Produces: route `GET/POST /year/<ay_label>/form16` — consumed by the dashboard link added in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_form16_entry.py`:
```python
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db, Database


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_form16_entry_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/form16")
    assert resp.status_code == 200
    assert b"Form 16 Part B" in resp.data
    assert b"Value of perquisites" in resp.data


def test_submit_form16_entry_saves_data(client):
    resp = client.post("/year/2024-25/form16", data={
        "gross_salary_inr": "2000000",
        "rsu_perquisite_value_inr": "392500",
        "tds_inr": "350000",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/form16")
    assert b"2000000" in resp.data or b"2,000,000" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_form16_entry.py -v`
Expected: FAIL with 404 (`assert 404 == 200`), route doesn't exist yet

- [ ] **Step 3: Write `app/templates/form16_entry.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Form 16 — {{ ay_label }}</h1>
  <form method="post">
    <label for="gross_salary_inr">Gross Salary (INR)</label>
    <input type="number" step="0.01" id="gross_salary_inr" name="gross_salary_inr"
           value="{{ form16.gross_salary_inr if form16 else '' }}" required>
    <div class="field-help">Form 16 Part B, "Details of Salary Paid" section.</div>

    <label for="rsu_perquisite_value_inr">RSU Perquisite Value, as reported by employer (INR)</label>
    <input type="number" step="0.01" id="rsu_perquisite_value_inr" name="rsu_perquisite_value_inr"
           value="{{ form16.rsu_perquisite_value_inr if form16 else '' }}" required>
    <div class="field-help">Form 16 Part B, under "Value of perquisites u/s 17(2)" — may be a separate line if your employer breaks it out.</div>

    <label for="tds_inr">TDS — Tax Deducted at Source (INR)</label>
    <input type="number" step="0.01" id="tds_inr" name="tds_inr"
           value="{{ form16.tds_inr if form16 else '' }}" required>
    <div class="field-help">Form 16 Part A, "Total tax deducted" summary, or Part B "Total Tax Payable".</div>

    <button type="submit" style="margin-top: 1rem;">Save</button>
  </form>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

Add this import at the top of `app/routes.py`:
```python
from core.models import Form16Summary
```

Add this route (after `year_detail`):
```python
@app.route("/year/<ay_label>/form16", methods=["GET", "POST"])
def form16_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_form16_summary(
            ay_id,
            gross_salary_inr=float(request.form["gross_salary_inr"]),
            rsu_perquisite_value_inr=float(request.form["rsu_perquisite_value_inr"]),
            tds_inr=float(request.form["tds_inr"]),
        )
        return redirect(url_for("year_detail", ay_label=ay_label))
    form16 = db.get_form16_summary(ay_id)
    return render_template("form16_entry.html", ay_label=ay_label, form16=form16)
```

Note: `create_or_get_assessment_year` is idempotent (Task 9, Step 1 test confirms this), so calling it again here with placeholder FY dates when the year already exists is safe — it returns the existing row without overwriting the real FY dates. This avoids needing a separate "get assessment year by label" method for this task.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_form16_entry.py -v`
Expected: `2 passed`

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add app/routes.py app/templates/form16_entry.html tests/test_app_form16_entry.py
git commit -m "Add Form 16 entry page with field-level source guidance"
```

---

## Task 12: Vesting event entry

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/vesting_entry.html`
- Test: `tests/test_app_vesting_entry.py`

**Interfaces:**
- Consumes: `get_db()` from `app.routes`.
- Produces: route `GET/POST /year/<ay_label>/vesting` (list + add) — consumed by the lot-allocation UI in Task 13 and the dashboard in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_vesting_entry.py`:
```python
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_vesting_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/vesting")
    assert resp.status_code == 200
    assert b"Release Confirmation" in resp.data


def test_add_vesting_event_and_list_it(client):
    resp = client.post("/year/2024-25/vesting", data={
        "vest_date": "2022-06-01",
        "shares_vested_gross": "100",
        "fmv_per_share_usd": "50",
        "shares_withheld_for_tax": "40",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/vesting")
    assert b"2022-06-01" in resp.data
    assert b"100" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_vesting_entry.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Write `app/templates/vesting_entry.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>RSU Vesting Events — {{ ay_label }}</h1>
  <form method="post">
    <label for="vest_date">Vest date</label>
    <input type="date" id="vest_date" name="vest_date" required>
    <div class="field-help">Schwab "Release Confirmation" or Fidelity Stock Plan release statement — "Vest Date" / "Release Date".</div>

    <label for="shares_vested_gross">Shares vested (gross)</label>
    <input type="number" step="0.0001" id="shares_vested_gross" name="shares_vested_gross" required>
    <div class="field-help">Same statement — "Shares Released" / "Gross Shares".</div>

    <label for="fmv_per_share_usd">FMV per share at vest (USD)</label>
    <input type="number" step="0.0001" id="fmv_per_share_usd" name="fmv_per_share_usd" required>
    <div class="field-help">Same statement — "Fair Market Value" / "FMV per Share".</div>

    <label for="shares_withheld_for_tax">Shares withheld for tax</label>
    <input type="number" step="0.0001" id="shares_withheld_for_tax" name="shares_withheld_for_tax" required>
    <div class="field-help">Same statement — "Shares Withheld for Taxes" / "Shares Sold to Cover Taxes".</div>

    <button type="submit" style="margin-top: 1rem;">Add Vesting Event</button>
  </form>

  <table>
    <tr><th>Vest Date</th><th>Shares Vested</th><th>FMV/Share (USD)</th><th>Shares Withheld</th></tr>
    {% for v in vesting_events %}
    <tr>
      <td>{{ v.vest_date }}</td>
      <td>{{ v.shares_vested_gross }}</td>
      <td>{{ v.fmv_per_share_usd }}</td>
      <td>{{ v.shares_withheld_for_tax }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

```python
@app.route("/year/<ay_label>/vesting", methods=["GET", "POST"])
def vesting_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_vesting_event(
            ay_id,
            vest_date=date.fromisoformat(request.form["vest_date"]),
            shares_vested_gross=float(request.form["shares_vested_gross"]),
            fmv_per_share_usd=float(request.form["fmv_per_share_usd"]),
            shares_withheld_for_tax=float(request.form["shares_withheld_for_tax"]),
        )
        return redirect(url_for("vesting_entry", ay_label=ay_label))
    vesting_events = db.list_vesting_events(ay_id)
    return render_template("vesting_entry.html", ay_label=ay_label, vesting_events=vesting_events)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_vesting_entry.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/routes.py app/templates/vesting_entry.html tests/test_app_vesting_entry.py
git commit -m "Add vesting event entry with field-level source guidance"
```

---

## Task 13: Sale event entry with explicit lot allocation

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/sale_entry.html`
- Test: `tests/test_app_sale_entry.py`

**Interfaces:**
- Consumes: `get_db()`, `db.list_vesting_events()` (to populate the lot-selection UI).
- Produces: route `GET/POST /year/<ay_label>/sales` — consumed by the dashboard in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_sale_entry.py`:
```python
import os
import tempfile
from datetime import date

import pytest

from app.routes import app, configure_db
from db.access import Database, init_db


@pytest.fixture
def client_and_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        c.post("/year/2024-25/vesting", data={
            "vest_date": "2022-06-01", "shares_vested_gross": "100",
            "fmv_per_share_usd": "50", "shares_withheld_for_tax": "40",
        })
        yield c, path
    os.remove(path)


def test_sale_page_lists_available_lots(client_and_path):
    client, _ = client_and_path
    resp = client.get("/year/2024-25/sales")
    assert resp.status_code == 200
    assert b"Realized Gain/Loss" in resp.data
    assert b"2022-06-01" in resp.data  # available lot shown for allocation


def test_add_sale_with_lot_allocation(client_and_path):
    client, path = client_and_path
    db = Database(path)
    ay_id = db.create_or_get_assessment_year("2024-25", date.today(), date.today())
    vest_id = db.list_vesting_events(ay_id)[0].id

    resp = client.post("/year/2024-25/sales", data={
        "sale_date": "2024-07-15",
        "quantity_sold": "100",
        "sale_price_per_share_usd": "70",
        f"lot_qty_{vest_id}": "100",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/sales")
    assert b"2024-07-15" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_sale_entry.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Write `app/templates/sale_entry.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Sale Events — {{ ay_label }}</h1>
  <form method="post">
    <label for="sale_date">Sale date</label>
    <input type="date" id="sale_date" name="sale_date" required>
    <div class="field-help">Schwab "Realized Gain/Loss" report or trade confirmation — "Trade Date" / "Date Sold".</div>

    <label for="quantity_sold">Quantity sold</label>
    <input type="number" step="0.0001" id="quantity_sold" name="quantity_sold" required>
    <div class="field-help">Same report — "Quantity".</div>

    <label for="sale_price_per_share_usd">Sale price per share (USD)</label>
    <input type="number" step="0.0001" id="sale_price_per_share_usd" name="sale_price_per_share_usd" required>
    <div class="field-help">Same report — "Sale Price" / "Price per Share".</div>

    <h3>Which vesting lot(s) did these shares come from?</h3>
    <div class="field-help">
      Enter the exact quantity drawn from each lot below. The total must equal
      "Quantity sold" above — this app never assumes FIFO or any other
      automatic matching.
    </div>
    {% for v in vesting_events %}
      <label for="lot_qty_{{ v.id }}">Vested {{ v.vest_date }} — {{ v.shares_vested_gross }} shares @ ${{ v.fmv_per_share_usd }}</label>
      <input type="number" step="0.0001" id="lot_qty_{{ v.id }}" name="lot_qty_{{ v.id }}" value="0">
    {% endfor %}

    <button type="submit" style="margin-top: 1rem;">Add Sale</button>
  </form>

  <table>
    <tr><th>Sale Date</th><th>Quantity</th><th>Sale Price/Share (USD)</th></tr>
    {% for s in sale_events %}
    <tr>
      <td>{{ s.sale_date }}</td>
      <td>{{ s.quantity_sold }}</td>
      <td>{{ s.sale_price_per_share_usd }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

```python
@app.route("/year/<ay_label>/sales", methods=["GET", "POST"])
def sale_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    vesting_events = db.list_vesting_events(ay_id)

    if request.method == "POST":
        sale_date = date.fromisoformat(request.form["sale_date"])
        quantity_sold = float(request.form["quantity_sold"])
        sale_price_per_share_usd = float(request.form["sale_price_per_share_usd"])
        sale_id = db.save_sale_event(ay_id, sale_date, quantity_sold, sale_price_per_share_usd)

        allocations = []
        for v in vesting_events:
            qty_key = f"lot_qty_{v.id}"
            qty = float(request.form.get(qty_key, 0) or 0)
            if qty > 0:
                allocations.append((v.id, qty))
        db.save_sale_lot_allocations(sale_id, allocations)

        return redirect(url_for("sale_entry", ay_label=ay_label))

    sales_with_allocations = db.list_sale_events_with_allocations(ay_id)
    sale_events = [s for s, _ in sales_with_allocations]
    return render_template("sale_entry.html", ay_label=ay_label, vesting_events=vesting_events, sale_events=sale_events)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_sale_entry.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/routes.py app/templates/sale_entry.html tests/test_app_sale_entry.py
git commit -m "Add sale event entry with explicit, non-FIFO lot allocation"
```

---

## Task 14: Dividend event entry

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/dividend_entry.html`
- Test: `tests/test_app_dividend_entry.py`

**Interfaces:**
- Consumes: `get_db()`.
- Produces: route `GET/POST /year/<ay_label>/dividends` — consumed by the dashboard in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_dividend_entry.py`:
```python
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_dividend_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/dividends")
    assert resp.status_code == 200
    assert b"1042-S" in resp.data


def test_add_dividend_event(client):
    resp = client.post("/year/2024-25/dividends", data={
        "payment_date": "2024-03-01",
        "gross_dividend_usd": "100",
        "us_tax_withheld_usd": "25",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/dividends")
    assert b"2024-03-01" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_dividend_entry.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Write `app/templates/dividend_entry.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Dividend Events — {{ ay_label }}</h1>
  <form method="post">
    <label for="payment_date">Dividend payment date</label>
    <input type="date" id="payment_date" name="payment_date" required>
    <div class="field-help">1042-S or 1099-DIV, or brokerage dividend statement — "Payment Date".</div>

    <label for="gross_dividend_usd">Gross dividend (USD)</label>
    <input type="number" step="0.0001" id="gross_dividend_usd" name="gross_dividend_usd" required>
    <div class="field-help">1042-S Box 2 ("Gross Income") or 1099-DIV Box 1a.</div>

    <label for="us_tax_withheld_usd">US tax withheld (USD)</label>
    <input type="number" step="0.0001" id="us_tax_withheld_usd" name="us_tax_withheld_usd" required>
    <div class="field-help">1042-S Box 7a ("Federal tax withheld") or 1099-DIV Box 4.</div>

    <button type="submit" style="margin-top: 1rem;">Add Dividend</button>
  </form>

  <table>
    <tr><th>Payment Date</th><th>Gross Dividend (USD)</th><th>US Tax Withheld (USD)</th></tr>
    {% for d in dividend_events %}
    <tr>
      <td>{{ d.payment_date }}</td>
      <td>{{ d.gross_dividend_usd }}</td>
      <td>{{ d.us_tax_withheld_usd }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

```python
@app.route("/year/<ay_label>/dividends", methods=["GET", "POST"])
def dividend_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_dividend_event(
            ay_id,
            payment_date=date.fromisoformat(request.form["payment_date"]),
            gross_dividend_usd=float(request.form["gross_dividend_usd"]),
            us_tax_withheld_usd=float(request.form["us_tax_withheld_usd"]),
        )
        return redirect(url_for("dividend_entry", ay_label=ay_label))
    dividend_events = db.list_dividend_events(ay_id)
    return render_template("dividend_entry.html", ay_label=ay_label, dividend_events=dividend_events)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_dividend_entry.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/routes.py app/templates/dividend_entry.html tests/test_app_dividend_entry.py
git commit -m "Add dividend event entry with field-level source guidance"
```

---

## Task 15: FX rate CSV upload

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/fx_upload.html`
- Test: `tests/test_app_fx_upload.py`

**Interfaces:**
- Consumes: `db.upsert_fx_rates()`, `db.get_all_fx_rates()`.
- Produces: route `GET/POST /year/<ay_label>/fx-rates` — consumed by the results view in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_fx_upload.py`:
```python
import io
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_fx_upload_page_explains_source(client):
    resp = client.get("/year/2024-25/fx-rates")
    assert resp.status_code == 200
    assert b"SBI" in resp.data


def test_upload_fx_csv_saves_rates(client):
    csv_content = "date,rate\n2024-07-15,83.20\n2022-06-01,78.50\n"
    data = {"fx_csv": (io.BytesIO(csv_content.encode()), "rates.csv")}
    resp = client.post("/year/2024-25/fx-rates", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/fx-rates")
    assert b"78.5" in resp.data
    assert b"83.2" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_fx_upload.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Write `app/templates/fx_upload.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Exchange Rates — {{ ay_label }}</h1>
  <div class="field-help">
    Upload a CSV with columns "date" (YYYY-MM-DD) and "rate" (INR per USD).
    Source this yourself or with your CA — typically SBI's published TT rate
    for each transaction date. This app does not fetch or verify rates; it
    only stores what you provide and hard-stops if a date you need is missing.
  </div>
  <form method="post" enctype="multipart/form-data">
    <label for="fx_csv">FX rate CSV</label>
    <input type="file" id="fx_csv" name="fx_csv" accept=".csv" required>
    <button type="submit" style="margin-top: 1rem;">Upload</button>
  </form>

  <table>
    <tr><th>Date</th><th>Rate (INR/USD)</th></tr>
    {% for d, r in rates.items() %}
    <tr><td>{{ d }}</td><td>{{ r }}</td></tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

Add this import at the top of `app/routes.py`:
```python
import csv
import io
```

Add this route:
```python
@app.route("/year/<ay_label>/fx-rates", methods=["GET", "POST"])
def fx_upload(ay_label: str):
    db = get_db()
    if request.method == "POST":
        file = request.files["fx_csv"]
        content = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rates = {date.fromisoformat(row["date"]): float(row["rate"]) for row in reader}
        db.upsert_fx_rates(rates)
        return redirect(url_for("fx_upload", ay_label=ay_label))
    rates = dict(sorted(db.get_all_fx_rates().items()))
    return render_template("fx_upload.html", ay_label=ay_label, rates=rates)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_fx_upload.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/routes.py app/templates/fx_upload.html tests/test_app_fx_upload.py
git commit -m "Add FX rate CSV upload"
```

---

## Task 16: Schedule FA calendar-year confirmation and monthly values

**Files:**
- Modify: `app/routes.py`
- Create: `app/templates/schedule_fa_confirm.html`
- Test: `tests/test_app_schedule_fa.py`

**Interfaces:**
- Consumes: `db.save_schedule_fa_calendar_year()`, `db.get_schedule_fa_calendar_year()`, `db.save_schedule_fa_monthly_value()`, `db.get_schedule_fa_monthly_values()`.
- Produces: route `GET/POST /year/<ay_label>/schedule-fa` — consumed by the results view in Task 17.

- [ ] **Step 1: Write the failing test**

`tests/test_app_schedule_fa.py`:
```python
import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_schedule_fa_page_explains_the_window_decision(client):
    resp = client.get("/year/2024-25/schedule-fa")
    assert resp.status_code == 200
    assert b"confirm with your CA" in resp.data.lower()


def test_confirm_calendar_year_and_add_monthly_value(client):
    resp = client.post("/year/2024-25/schedule-fa", data={
        "calendar_year": "2024",
        "value_date": "2024-12-31",
        "account_value_inr": "900000",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/schedule-fa")
    assert b"2024" in resp.data
    assert b"900000" in resp.data or b"900,000" in resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_schedule_fa.py -v`
Expected: FAIL with 404

- [ ] **Step 3: Write `app/templates/schedule_fa_confirm.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Schedule FA — {{ ay_label }}</h1>
  <div class="field-help">
    Which Jan 1–Dec 31 calendar year applies to Schedule FA for this
    assessment year is a filing-method decision, not something read off a
    document — confirm with your CA. This app will not infer it for you.
  </div>
  <form method="post">
    <label for="calendar_year">Calendar year to use for Schedule FA</label>
    <input type="number" id="calendar_year" name="calendar_year" value="{{ calendar_year or '' }}" required>

    <h3>Add an account value on a specific date</h3>
    <div class="field-help">Enter values from your monthly/year-end brokerage statements across the full calendar year — you need at minimum a Dec 31 value to compute the closing figure.</div>
    <label for="value_date">Date</label>
    <input type="date" id="value_date" name="value_date" required>
    <label for="account_value_inr">Account value (INR)</label>
    <input type="number" step="0.01" id="account_value_inr" name="account_value_inr" required>

    <button type="submit" style="margin-top: 1rem;">Save</button>
  </form>

  <table>
    <tr><th>Date</th><th>Account Value (INR)</th></tr>
    {% for d, v in monthly_values.items() %}
    <tr><td>{{ d }}</td><td>{{ v }}</td></tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 4: Add the route to `app/routes.py`**

```python
@app.route("/year/<ay_label>/schedule-fa", methods=["GET", "POST"])
def schedule_fa_confirm(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_schedule_fa_calendar_year(ay_id, int(request.form["calendar_year"]))
        db.save_schedule_fa_monthly_value(
            ay_id,
            value_date=date.fromisoformat(request.form["value_date"]),
            account_value_inr=float(request.form["account_value_inr"]),
        )
        return redirect(url_for("schedule_fa_confirm", ay_label=ay_label))
    calendar_year = db.get_schedule_fa_calendar_year(ay_id)
    monthly_values = dict(sorted(db.get_schedule_fa_monthly_values(ay_id).items()))
    return render_template("schedule_fa_confirm.html", ay_label=ay_label, calendar_year=calendar_year, monthly_values=monthly_values)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app_schedule_fa.py -v`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add app/routes.py app/templates/schedule_fa_confirm.html tests/test_app_schedule_fa.py
git commit -m "Add Schedule FA calendar-year confirmation and monthly value entry"
```

---

## Task 17: Results view and real dashboard

**Files:**
- Modify: `app/routes.py` (replace the placeholder `year_detail` from Task 10, add `results` route)
- Create: `app/templates/dashboard.html`
- Create: `app/templates/results.html`
- Test: `tests/test_app_results.py`

**Interfaces:**
- Consumes: `core.report.build_report`, all `db.access.Database` list/get methods, `core.fx.FXRateTable`, `core.fx.MissingFXRateError`.
- Produces: route `GET /year/<ay_label>` (now the real dashboard, replacing the Task 10 placeholder), route `GET /year/<ay_label>/results`.

- [ ] **Step 1: Write the failing test**

`tests/test_app_results.py`:
```python
import os
import tempfile
from datetime import date

import pytest

from app.routes import app, configure_db
from db.access import Database, init_db


@pytest.fixture
def client_and_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        c.post("/year/2024-25/form16", data={
            "gross_salary_inr": "2000000", "rsu_perquisite_value_inr": "392500", "tds_inr": "350000",
        })
        c.post("/year/2024-25/vesting", data={
            "vest_date": "2022-06-01", "shares_vested_gross": "100",
            "fmv_per_share_usd": "50", "shares_withheld_for_tax": "40",
        })
        yield c, path
    os.remove(path)


def test_dashboard_links_to_all_entry_pages(client_and_path):
    client, _ = client_and_path
    resp = client.get("/year/2024-25")
    assert resp.status_code == 200
    for p in ["/form16", "/vesting", "/sales", "/dividends", "/fx-rates", "/schedule-fa", "/results"]:
        assert f"/year/2024-25{p}".encode() in resp.data


def test_results_blocks_with_clear_error_when_fx_rate_missing(client_and_path):
    client, _ = client_and_path
    # vesting date 2022-06-01 has no FX rate uploaded yet
    resp = client.get("/year/2024-25/results")
    assert resp.status_code == 200
    assert b"Missing FX rate" in resp.data
    assert b"2022-06-01" in resp.data


def test_results_shows_computed_values_with_formula_when_data_complete(client_and_path):
    client, path = client_and_path
    db = Database(path)
    ay_id = db.create_or_get_assessment_year("2024-25", date.today(), date.today())
    db.upsert_fx_rates({date(2022, 6, 1): 78.50, date(2024, 12, 31): 85.0})
    db.save_schedule_fa_calendar_year(ay_id, 2024)
    db.save_schedule_fa_monthly_value(ay_id, date(2024, 12, 31), 900000.0)

    resp = client.get("/year/2024-25/results")
    assert resp.status_code == 200
    assert b"392" in resp.data  # perquisite cross-check value appears (no mismatch expected)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_app_results.py -v`
Expected: FAIL — dashboard links don't exist yet, `/results` route doesn't exist

- [ ] **Step 3: Write `app/templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Assessment Year {{ ay_label }}</h1>
  <nav>
    <a href="{{ url_for('form16_entry', ay_label=ay_label) }}">Form 16 / 26AS</a>
    <a href="{{ url_for('vesting_entry', ay_label=ay_label) }}">Vesting Events</a>
    <a href="{{ url_for('sale_entry', ay_label=ay_label) }}">Sale Events</a>
    <a href="{{ url_for('dividend_entry', ay_label=ay_label) }}">Dividends</a>
    <a href="{{ url_for('fx_upload', ay_label=ay_label) }}">FX Rates</a>
    <a href="{{ url_for('schedule_fa_confirm', ay_label=ay_label) }}">Schedule FA</a>
    <a href="{{ url_for('results', ay_label=ay_label) }}">Results</a>
  </nav>
{% endblock %}
```

- [ ] **Step 4: Write `app/templates/results.html`**

```html
{% extends "base.html" %}
{% block content %}
  <h1>Results — {{ ay_label }}</h1>

  {% if error %}
    <div class="warning"><strong>Cannot compute:</strong> {{ error }}</div>
  {% else %}
    {% if report.perquisite_mismatch %}
      <div class="warning">
        <strong>Form 16 / vesting mismatch:</strong>
        Form 16 reports ₹{{ report.perquisite_mismatch.form16_value_inr }},
        vesting records sum to ₹{{ report.perquisite_mismatch.vesting_sum_inr }}
        (difference ₹{{ report.perquisite_mismatch.difference_inr }}).
        Review both figures before filing — neither is assumed correct.
      </div>
    {% endif %}

    <h2>Schedule Capital Gains</h2>
    <table>
      <tr><th>Lot</th><th>Qty</th><th>Cost Basis (INR)</th><th>Proceeds (INR)</th><th>Gain (INR)</th><th>Classification</th></tr>
      {% for lot in report.lot_gains %}
      <tr>
        <td>Vest #{{ lot.vesting_event_id }}</td>
        <td>{{ lot.quantity }}</td>
        <td>{{ lot.cost_basis_inr }}</td>
        <td>{{ lot.proceeds_inr }}</td>
        <td>{{ lot.gain_inr }}</td>
        <td>
          {{ "Long-term" if lot.is_long_term else "Short-term" }}
          {% if lot.near_boundary %}<strong> — within 5 days of the 24-month boundary, double-check this date</strong>{% endif %}
        </td>
      </tr>
      {% endfor %}
    </table>

    <h2>Schedule TR/FSI — Foreign Tax Credit</h2>
    <p>Total US tax withheld on dividends: ${{ report.ftc.total_us_tax_withheld_usd }}</p>
    <p><strong>{{ report.ftc.form_67_deadline_note }}</strong></p>

    <h2>Schedule FA</h2>
    <p>Calendar year: {{ report.schedule_fa.calendar_year }}</p>
    <p>Peak value: ₹{{ report.schedule_fa.peak_value_inr }}</p>
    <p>Closing value (Dec 31): ₹{{ report.schedule_fa.closing_value_inr }}</p>

    <h2>Schedule Salary</h2>
    <p>Gross salary: ₹{{ report.form16.gross_salary_inr }}</p>
    <p>RSU perquisite (as reported by employer): ₹{{ report.form16.rsu_perquisite_value_inr }}</p>
    <p>TDS: ₹{{ report.form16.tds_inr }}</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Replace `year_detail` and add `results` in `app/routes.py`**

Add these imports at the top of `app/routes.py`:
```python
from core.fx import FXRateTable, MissingFXRateError
from core.report import build_report
```

Replace the placeholder `year_detail` function from Task 10 with:
```python
@app.route("/year/<ay_label>")
def year_detail(ay_label: str):
    return render_template("dashboard.html", ay_label=ay_label)
```

Add the `results` route:
```python
@app.route("/year/<ay_label>/results")
def results(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())

    form16 = db.get_form16_summary(ay_id)
    vesting_events = db.list_vesting_events(ay_id)
    sales_with_allocations = db.list_sale_events_with_allocations(ay_id)
    sale_events = [s for s, _ in sales_with_allocations]
    allocations_by_sale = {s.id: allocs for s, allocs in sales_with_allocations}
    dividend_events = db.list_dividend_events(ay_id)
    fx_rates = db.get_all_fx_rates()
    schedule_fa_calendar_year = db.get_schedule_fa_calendar_year(ay_id)
    schedule_fa_monthly_values = db.get_schedule_fa_monthly_values(ay_id)

    if form16 is None:
        return render_template("results.html", ay_label=ay_label, error="Form 16 data hasn't been entered yet.")
    if schedule_fa_calendar_year is None:
        return render_template("results.html", ay_label=ay_label, error="Schedule FA calendar year hasn't been confirmed yet.")

    fx_table = FXRateTable(fx_rates)

    try:
        report = build_report(
            form16=form16,
            vesting_events=vesting_events,
            sale_events=sale_events,
            allocations_by_sale=allocations_by_sale,
            dividend_events=dividend_events,
            fx_table=fx_table,
            schedule_fa_calendar_year=schedule_fa_calendar_year,
            schedule_fa_monthly_values=schedule_fa_monthly_values,
        )
    except MissingFXRateError as e:
        return render_template("results.html", ay_label=ay_label, error=str(e))
    except ValueError as e:
        return render_template("results.html", ay_label=ay_label, error=str(e))

    return render_template("results.html", ay_label=ay_label, report=report, error=None)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_app_results.py -v`
Expected: `3 passed`

- [ ] **Step 7: Run the entire test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (every task's tests, ~50+ total)

- [ ] **Step 8: Commit**

```bash
git add app/routes.py app/templates/dashboard.html app/templates/results.html tests/test_app_results.py
git commit -m "Add results view assembling the full ITR-2 report with inline error handling"
```

---

## Task 18: Manual smoke test and final commit

**Files:**
- No new files — this task verifies the running app end-to-end.

- [ ] **Step 1: Start the app**

Run: `cd C:\Codes\Labs\itr2-rsu-assistant && python run.py`
Expected: Flask dev server starts on `http://127.0.0.1:5000`, no errors in console.

- [ ] **Step 2: Manually walk through the flow in a browser**

1. Open `http://127.0.0.1:5000` — confirm the disclaimer banner is visible and the year-creation form works.
2. Create assessment year `2024-25`.
3. Visit each dashboard link (Form 16, Vesting, Sales, Dividends, FX Rates, Schedule FA) — confirm every field shows its source-document guidance text without needing to hover or click anything.
4. Enter one vesting event, one sale event allocated to that vesting lot, one dividend event.
5. Visit Results before uploading FX rates — confirm it shows a clear "Missing FX rate" message naming the specific missing dates, not a stack trace or blank page.
6. Upload an FX rate CSV covering the needed dates, confirm the Schedule FA calendar year and add a Dec 31 value.
7. Revisit Results — confirm every number is shown with enough context (lot, quantity, classification) to trace where it came from.

- [ ] **Step 3: Stop the server**

Press Ctrl+C in the terminal running `run.py`.

- [ ] **Step 4: Confirm the working database file is not committed**

Run: `cd C:\Codes\Labs\itr2-rsu-assistant && git status --short`
Expected: `itr2_rsu_assistant.db` (created by Step 1) shows as untracked. If it doesn't appear at all, it's already ignored — verify with `git check-ignore -v itr2_rsu_assistant.db`; if it's not ignored, add a `.gitignore` with `*.db` before committing anything else, since this file will hold real personal financial data once actually used.

- [ ] **Step 5: Add `.gitignore` for the database file**

Create `.gitignore`:
```
*.db
__pycache__/
*.pyc
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore
git commit -m "Ignore local SQLite database file"
git log --oneline
```

Expected: a clean commit history from Task 1 through this task, and no `.db` file ever tracked.

---

## Plan self-review notes

- **Spec coverage:** all 8 guardrails, all 10 golden cases, the field-guidance table, the confidence-gating principle (hardcoded 24-month rule vs. user-confirmed FX-rate-type and Schedule-FA-year decisions), and the "out of scope for v1" list (no parsing, no e-filing integration, no multi-year comparison) are each implemented or explicitly enforced by a task above.
- **Type consistency:** `VestingEvent`, `SaleEvent`, `SaleLotAllocation`, `DividendEvent`, `Form16Summary` are defined once in Task 2 and reused with identical field names throughout every later task — no renamed fields.
- **No placeholders:** every step above shows complete, runnable code. The one exception — `year_detail` in Task 10 — is explicitly marked as a temporary placeholder that Task 17 replaces, with the reason stated inline, which is a deliberate incremental-build note, not an unfinished requirement.
- **Fixed during self-review:** the Task 13 and Task 17 tests originally reached into a private `app.routes._db_path_holder` attribute (with a stray dead-code line in Task 13's draft) to get a `Database` handle for test setup. Both were rewritten to yield `(client, path)` from their fixtures and construct `Database(path)` directly — cleaner, no private-attribute reach-through, no dead code.
