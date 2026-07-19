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
