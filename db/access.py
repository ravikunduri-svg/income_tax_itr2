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
