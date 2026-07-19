import re
from datetime import datetime

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


def parse(pdf_path: str, password: str = "") -> ParseResult:
    text = _extract_text(pdf_path, password)
    return {
        "vest_date": _parse_vest_date(text),
        "shares_vested_gross": _parse_shares_released(text),
        "fmv_per_share_usd": _parse_fmv(text),
        "shares_withheld_for_tax": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str, password: str = "") -> str:
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_vest_date(text: str) -> ParsedField:
    m = re.search(r"Release Date[:\s]+([\d/]+)", text, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        try:
            d = datetime.strptime(raw, "%m/%d/%Y")
            return high(d.strftime("%Y-%m-%d"), "label 'Release Date'")
        except ValueError:
            return medium(raw, "label 'Release Date' (unexpected date format)")
    return missing("vest_date")


def _parse_shares_released(text: str) -> ParsedField:
    m = re.search(r"Shares Released[:\s]+([\d,]+)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Shares Released'")
    return missing("shares_vested_gross")


def _parse_fmv(text: str) -> ParsedField:
    # Schwab: "Fair Market Value at Release: $1,285.75 per share"
    m = re.search(
        r"Fair Market Value at Release[:\s]+\$?([\d,]+\.?\d*)\s*per share",
        text,
        re.IGNORECASE,
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Fair Market Value at Release'")
    m = re.search(r"Fair Market Value[^:\n]*[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'Fair Market Value'")
    return missing("fmv_per_share_usd")


def _parse_tax_withheld(text: str) -> ParsedField:
    m = re.search(r"Shares Withheld for Tax[:\s]+([\d,]+)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Shares Withheld for Tax'")
    return missing("shares_withheld_for_tax")
