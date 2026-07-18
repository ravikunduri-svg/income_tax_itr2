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
        yield c
    os.remove(path)


def test_index_shows_year_select_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Assessment Year" in resp.data


def test_create_new_assessment_year_redirects_to_it(client):
    resp = client.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
    assert resp.status_code == 302
    assert "/year/2024-25" in resp.headers["Location"]


def test_reopen_existing_assessment_year(client):
    client.post("/", data={"ay_label": "2024-25", "fy_start_date": "2024-04-01", "fy_end_date": "2025-03-31"})
    resp = client.get("/year/2024-25")
    assert resp.status_code == 200
    assert b"2024-25" in resp.data
