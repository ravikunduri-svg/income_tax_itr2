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
        c.post("/year/2024-25/vesting", data={
            "vest_date": "2022-06-01", "shares_vested_gross": "100",
            "fmv_per_share_usd": "50", "shares_withheld_for_tax": "40",
        })
        yield c, path
    os.remove(path)


def test_sale_page_lists_available_lots(client_and_path):
    client, _ = client_and_path
    resp = client.get("/year/2024-25/sales")
    assert resp.status_code == 200
    assert b"Lot allocation" in resp.data
    assert b"2022-06-01" in resp.data  # available lot shown for allocation


def test_add_sale_with_lot_allocation(client_and_path):
    client, path = client_and_path
    db = Database(path)
    ay_id = db.create_or_get_assessment_year("2024-25", date.today(), date.today())
    vest_id = db.list_vesting_events(ay_id)[0].id

    resp = client.post("/year/2024-25/sales", data={
        "sale_date": "2024-07-15",
        "quantity_sold": "100",
        "sale_price_per_share_usd": "70",
        f"lot_qty_{vest_id}": "100",
    })
    assert resp.status_code == 302

    resp = client.get("/year/2024-25/sales")
    assert b"2024-07-15" in resp.data
