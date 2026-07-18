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
