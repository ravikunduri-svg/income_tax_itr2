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
