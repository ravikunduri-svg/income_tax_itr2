import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, missing


def parse(pdf_path: str, password: str = "") -> ParseResult:
    text = _extract_text(pdf_path, password)
    return {
        "gross_dividend_usd": _parse_gross_income(text),
        "us_tax_withheld_usd": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str, password: str = "") -> str:
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_gross_income(text: str) -> ParsedField:
    # 1042-S Box 2: "2. Gross Income: 1250.00"
    m = re.search(r"2\.?\s*Gross Income[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label '2. Gross Income' (1042-S)")
    return missing("gross_dividend_usd")


def _parse_tax_withheld(text: str) -> ParsedField:
    # 1042-S Box 7a: "7a. Federal Tax Withheld: 375.00"
    m = re.search(r"7a\.?\s*Federal Tax Withheld[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label '7a. Federal Tax Withheld' (1042-S)")
    return missing("us_tax_withheld_usd")
