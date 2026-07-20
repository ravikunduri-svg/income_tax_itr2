import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


def parse(pdf_path: str, password: str = "") -> ParseResult:
    text = _extract_text(pdf_path, password)
    return {
        "gross_salary_inr": _parse_gross_salary(text),
        "rsu_perquisite_value_inr": _parse_perquisite(text),
        "tds_inr": _parse_tds(text),
    }


def _extract_text(pdf_path: str, password: str = "") -> str:
    with pdfplumber.open(pdf_path, password=password or None) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_gross_salary(text: str) -> ParsedField:
    # Part B row (d): "(d) Total 93200840.00" — sum of 17(1)+17(2)+17(3)
    m = re.search(r"\(d\)\s+Total\s+([\d,]+\.?\d*)", text)
    if m:
        return high(float(m.group(1).replace(",", "")), "Part B row (d) Total gross salary")
    # Older format with colon separator
    m = re.search(r"Salary as per provisions[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Salary as per provisions'")
    m = re.search(r"Gross Salary[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'Gross Salary'")
    return missing("gross_salary_inr")


def _parse_perquisite(text: str) -> ParsedField:
    # Part B: label on one line, value on next as "(b) <value>"
    m = re.search(
        r"Value of perquisites under section 17\(2\)[^\n]*\n\s*\(b\)\s+([\d,]+\.?\d*)",
        text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "Part B row (b) Value of perquisites u/s 17(2)")
    # Form 12BA row 21: "Total Value of Perquisites <value>"
    m = re.search(r"Total Value of Perquisites\s+([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "Form 12BA row 21 Total Value of Perquisites")
    # Older colon-separated format
    m = re.search(r"Value of perquisites u/s 17\(2\)[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Value of perquisites u/s 17(2)'")
    m = re.search(r"perquisites[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'perquisites'")
    return missing("rsu_perquisite_value_inr")


def _parse_tds(text: str) -> ParsedField:
    # Form 12BA: "Tax Deducted from Salary of Employee u/s 192(1) 3,57,73,078.00"
    m = re.search(
        r"Tax Deducted from Salary of Employee u/s 192\(1\)\s+([\d,]+\.?\d*)",
        text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "Form 12BA row (a) Tax Deducted u/s 192(1)")
    # Part A quarterly summary: "Total (Rs.) <paid> <deducted> <deposited>"
    m = re.search(r"Total \(Rs\.\)\s+[\d,]+\.?\d*\s+([\d,]+\.?\d*)", text)
    if m:
        return high(float(m.group(1).replace(",", "")), "Part A quarterly TDS Total")
    # Older formats
    m = re.search(r"Total amount of tax deducted[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Total amount of tax deducted'")
    m = re.search(r"Tax Deducted[^:\n]*:\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m:
        return medium(float(m.group(1).replace(",", "")), "label 'Tax Deducted'")
    return missing("tds_inr")
