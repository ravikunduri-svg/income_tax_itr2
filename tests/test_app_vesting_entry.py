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


def test_vesting_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/vesting")
    assert resp.status_code == 200
    assert b"Release Confirmation" in resp.data


def test_add_vesting_event_and_list_it(client):
    resp = client.post("/year/2024-25/vesting", data={
        "vest_date": "2022-06-01",
        "shares_vested_gross": "100",
        "fmv_per_share_usd": "50",
        "shares_withheld_for_tax": "40",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/vesting")
    assert b"2022-06-01" in resp.data
    assert b"100" in resp.data
