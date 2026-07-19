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
