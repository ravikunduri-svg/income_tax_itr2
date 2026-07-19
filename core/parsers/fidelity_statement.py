import re
from datetime import datetime

import pdfplumber


def parse(pdf_path: str, password: str = "") -> dict:
    text = _extract_text(pdf_path, password)
    return {
        "vesting_events": _parse_vesting_events(text),
        "sale_events": _parse_sale_events(text),
    }


def _extract_text(pdf_path: str, password: str = "") -> str:
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_vesting_events(text: str) -> list:
    events = []
    vest_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+RSU VEST\s+\w+\s+([\d,]+)\s+([\d,]+\.?\d*)", re.IGNORECASE
    )
    for m in vest_pattern.finditer(text):
        vest_date = datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        shares = float(m.group(2).replace(",", ""))
        fmv = float(m.group(3).replace(",", ""))
        tax_pattern = re.compile(
            rf"{re.escape(m.group(1))}\s+TAX WITHHOLDING SELL\s+\w+\s+([\d,]+)", re.IGNORECASE
        )
        tax_m = tax_pattern.search(text)
        tax_shares = float(tax_m.group(1).replace(",", "")) if tax_m else 0.0
        events.append({
            "vest_date": vest_date,
            "shares_vested_gross": shares,
            "fmv_per_share_usd": fmv,
            "shares_withheld_for_tax": tax_shares,
            "confidence": "high" if tax_m else "medium",
        })
    return events


def _parse_sale_events(text: str) -> list:
    events = []
    pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+YOU SOLD\s+\w+\s+([\d,]+)\s+([\d,]+\.?\d*)", re.IGNORECASE
    )
    for m in pattern.finditer(text):
        events.append({
            "sale_date": datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d"),
            "shares_sold": float(m.group(2).replace(",", "")),
            "price_per_share_usd": float(m.group(3).replace(",", "")),
            "confidence": "high",
        })
    return events
