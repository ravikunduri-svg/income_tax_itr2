import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db


@pytest.fixture
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    configure_db(path)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
        yield c
    os.remove(path)


def test_schedule_fa_page_explains_the_window_decision(client):
    resp = client.get("/year/2024-25/schedule-fa")
    assert resp.status_code == 200
    assert b"confirm with your CA" in resp.data.lower()


def test_confirm_calendar_year_and_add_monthly_value(client):
    resp = client.post("/year/2024-25/schedule-fa", data={
        "calendar_year": "2024",
        "value_date": "2024-12-31",
        "account_value_inr": "900000",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/schedule-fa")
    assert b"2024" in resp.data
    assert b"900000" in resp.data or b"900,000" in resp.data
