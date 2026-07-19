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
