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
