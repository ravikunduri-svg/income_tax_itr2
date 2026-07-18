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
