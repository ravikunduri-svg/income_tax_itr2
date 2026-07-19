import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {
        "gross_salary_inr": _parse_gross_salary(text),
        "rsu_perquisite_value_inr": _parse_perquisite(text),
        "tds_inr": _parse_tds(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_gross_salary(text: str) -> ParsedField:
    m = re.search(
        r"Salary as per provisions[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Salary as per provisions'")
    m = re.search(r"Gross Salary[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'Gross Salary'")
    return missing("gross_salary_inr")


def _parse_perquisite(text: str) -> ParsedField:
    m = re.search(
        r"Value of perquisites u/s 17\(2\)[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Value of perquisites u/s 17(2)'")
    m = re.search(r"perquisites[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'perquisites'")
    return missing("rsu_perquisite_value_inr")


def _parse_tds(text: str) -> ParsedField:
    m = re.search(
        r"Total amount of tax deducted[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Total amount of tax deducted'")
    m = re.search(r"Tax Deducted[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'Tax Deducted'")
    return missing("tds_inr")
