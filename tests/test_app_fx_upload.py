import io
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


def test_fx_upload_page_explains_source(client):
    resp = client.get("/year/2024-25/fx-rates")
    assert resp.status_code == 200
    assert b"SBI" in resp.data


def test_upload_fx_csv_saves_rates(client):
    csv_content = "date,rate\n2024-07-15,83.20\n2022-06-01,78.50\n"
    data = {"fx_csv": (io.BytesIO(csv_content.encode()), "rates.csv")}
    resp = client.post("/year/2024-25/fx-rates", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/fx-rates")
    assert b"78.5" in resp.data
    assert b"83.2" in resp.data
