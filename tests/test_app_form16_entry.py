import os
import tempfile

import pytest

from app.routes import app, configure_db
from db.access import init_db, Database


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


def test_form16_entry_page_shows_field_guidance(client):
    resp = client.get("/year/2024-25/form16")
    assert resp.status_code == 200
    assert b"Form 16 Part B" in resp.data
    assert b"Value of perquisites" in resp.data


def test_submit_form16_entry_saves_data(client):
    resp = client.post("/year/2024-25/form16", data={
        "gross_salary_inr": "2000000",
        "rsu_perquisite_value_inr": "392500",
        "tds_inr": "350000",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/form16")
    assert b"2000000" in resp.data or b"2,000,000" in resp.data
