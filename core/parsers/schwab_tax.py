import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {
        "gross_dividend_usd": _parse_dividend(text),
        "us_tax_withheld_usd": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_dividend(text: str) -> ParsedField:
    # 1099-DIV Box 1a: "1a. Total ordinary dividends: $850.00"
    m = re.search(
        r"1a\.?\s*Total ordinary dividends[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label '1a. Total ordinary dividends' (1099-DIV)")
    return missing("gross_dividend_usd")


def _parse_tax_withheld(text: str) -> ParsedField:
    # 1099-DIV Box 4: "4. Federal income tax withheld: $0.00"
    m = re.search(
        r"4\.?\s*Federal income tax withheld[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label '4. Federal income tax withheld' (1099-DIV)")
    return missing("us_tax_withheld_usd")
