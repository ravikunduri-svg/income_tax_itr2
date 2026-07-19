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


def test_dividend_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/dividends")
    assert resp.status_code == 200
    assert b"1042-S" in resp.data


def test_add_dividend_event(client):
    resp = client.post("/year/2024-25/dividends", data={
        "payment_date": "2024-03-01",
        "gross_dividend_usd": "100",
        "us_tax_withheld_usd": "25",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/dividends")
    assert b"2024-03-01" in resp.data
