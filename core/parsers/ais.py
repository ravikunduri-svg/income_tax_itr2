import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {"tds_inr": _parse_tds(text)}


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_tds(text: str) -> ParsedField:
    m = re.search(r"Tax Deducted[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Tax Deducted'")
    return missing("tds_inr")
