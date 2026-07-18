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
