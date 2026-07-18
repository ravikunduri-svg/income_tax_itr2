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
