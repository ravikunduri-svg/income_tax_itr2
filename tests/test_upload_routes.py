import io
import os
import tempfile
from unittest.mock import patch

import pytest

from app.routes import app, configure_db
from core.parsers._base import ParsedField
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


_MINIMAL_PDF = b"%PDF-1.4\n%%EOF"


def _pf(value, confidence="high"):
    return ParsedField(value=value, confidence=confidence, source_hint="test")


# --- Form 16 upload ---

def test_form16_upload_stores_prefill_in_session(client):
    mock_result = {
        "gross_salary_inr": _pf(3500000.0),
        "rsu_perquisite_value_inr": _pf(392500.0),
        "tds_inr": _pf(350000.0),
    }
    with patch("core.parsers.detect.detect_document_type", return_value="form16"), \
         patch("core.parsers.form16.parse", return_value=mock_result):
        resp = client.post(
            "/year/2024-25/form16/upload",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "form16.pdf")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 302
    resp2 = client.get("/year/2024-25/form16")
    assert b"3500000" in resp2.data
    assert b"392500" in resp2.data


def test_form16_upload_ais_shows_crosscheck(client):
    mock_result = {"tds_inr": _pf(350000.0)}
    with patch("core.parsers.detect.detect_document_type", return_value="ais"), \
         patch("core.parsers.ais.parse", return_value=mock_result):
        client.post(
            "/year/2024-25/form16/upload",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "ais.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/year/2024-25/form16")
    assert b"AIS cross-check" in resp.data
    assert b"350000" in resp.data


def test_form16_upload_unknown_type_flashes_error(client):
    with patch("core.parsers.detect.detect_document_type", return_value="unknown"):
        client.post(
            "/year/2024-25/form16/upload",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "other.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/year/2024-25/form16")
    assert b"Unrecognised" in resp.data or b"Expected" in resp.data


# --- Vesting upload ---

def test_vesting_upload_release_stores_prefill(client):
    mock_result = {
        "vest_date": _pf("2023-10-15"),
        "shares_vested_gross": _pf(100.0),
        "fmv_per_share_usd": _pf(785.50),
        "shares_withheld_for_tax": _pf(30.0),
    }
    with patch("core.parsers.detect.detect_document_type", return_value="fidelity_release"), \
         patch("core.parsers.fidelity_release.parse", return_value=mock_result):
        resp = client.post(
            "/year/2024-25/vesting/upload",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "release.pdf")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 302
    resp2 = client.get("/year/2024-25/vesting")
    assert b"2023-10-15" in resp2.data
    assert b"785" in resp2.data


def test_vesting_upload_bulk_shows_review_table(client):
    mock_result = {
        "vesting_events": [
            {"vest_date": "2023-10-15", "shares_vested_gross": 100.0,
             "fmv_per_share_usd": 785.50, "shares_withheld_for_tax": 30.0, "confidence": "high"}
        ],
        "sale_events": [],
    }
    with patch("core.parsers.detect.detect_document_type", return_value="fidelity_statement"), \
         patch("core.parsers.fidelity_statement.parse", return_value=mock_result):
        client.post(
            "/year/2024-25/vesting/upload-bulk",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "statement.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/year/2024-25/vesting")
    assert b"Review extracted vesting events" in resp.data
    assert b"2023-10-15" in resp.data


def test_vesting_bulk_save_selected_rows(client):
    mock_result = {
        "vesting_events": [
            {"vest_date": "2023-10-15", "shares_vested_gross": 100.0,
             "fmv_per_share_usd": 785.50, "shares_withheld_for_tax": 30.0, "confidence": "high"},
            {"vest_date": "2024-01-15", "shares_vested_gross": 50.0,
             "fmv_per_share_usd": 900.0, "shares_withheld_for_tax": 15.0, "confidence": "high"},
        ],
        "sale_events": [],
    }
    with patch("core.parsers.detect.detect_document_type", return_value="fidelity_statement"), \
         patch("core.parsers.fidelity_statement.parse", return_value=mock_result):
        client.post(
            "/year/2024-25/vesting/upload-bulk",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "statement.pdf")},
            content_type="multipart/form-data",
        )
    # Save only row 0 (not row 1)
    resp = client.post(
        "/year/2024-25/vesting",
        data={"action": "save_bulk", "selected_rows": "0"},
    )
    assert resp.status_code == 302
    resp2 = client.get("/year/2024-25/vesting")
    assert b"2023-10-15" in resp2.data  # saved
    assert b"2024-01-15" not in resp2.data  # not saved


# --- Sales upload ---

def test_sales_upload_bulk_shows_review_table(client):
    mock_result = {
        "vesting_events": [],
        "sale_events": [
            {"sale_date": "2023-11-20", "shares_sold": 70.0,
             "price_per_share_usd": 810.25, "confidence": "high"}
        ],
    }
    with patch("core.parsers.detect.detect_document_type", return_value="fidelity_statement"), \
         patch("core.parsers.fidelity_statement.parse", return_value=mock_result):
        client.post(
            "/year/2024-25/sales/upload-bulk",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "statement.pdf")},
            content_type="multipart/form-data",
        )
    resp = client.get("/year/2024-25/sales")
    assert b"Review extracted sale events" in resp.data
    assert b"2023-11-20" in resp.data


# --- Dividends upload ---

def test_dividends_upload_stores_prefill(client):
    mock_result = {
        "gross_dividend_usd": _pf(1250.0),
        "us_tax_withheld_usd": _pf(375.0),
    }
    with patch("core.parsers.detect.detect_document_type", return_value="fidelity_tax"), \
         patch("core.parsers.fidelity_tax.parse", return_value=mock_result):
        resp = client.post(
            "/year/2024-25/dividends/upload",
            data={"pdf": (io.BytesIO(_MINIMAL_PDF), "1042s.pdf")},
            content_type="multipart/form-data",
        )
    assert resp.status_code == 302
    resp2 = client.get("/year/2024-25/dividends")
    assert b"1250" in resp2.data
    assert b"375" in resp2.data
