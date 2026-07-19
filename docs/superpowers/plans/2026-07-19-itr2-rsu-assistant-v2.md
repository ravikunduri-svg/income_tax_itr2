# ITR-2 RSU Assistant v2 — PDF Upload & Auto-Population Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend v1 with local PDF parsing so Form 16, AIS, Fidelity, and Schwab PDFs auto-populate the existing entry forms with per-field confidence indicators.

**Architecture:** A new `core/parsers/` package (pdfplumber + regex, no network) exposes one `parse(pdf_path) -> ParseResult` function per document type. Upload routes in `app/routes.py` call the right parser, store results in Flask session, and redirect to the existing entry form. Templates show a confidence dot (green/yellow/orange/red) next to each pre-filled field. Manual entry still works unchanged.

**Tech Stack:** Python 3.11+, Flask 3.x, pdfplumber ≥0.11, stdlib re/datetime, pytest. All existing v1 constraints remain.

**Working directory for all commands:** `C:\Codes\Labs\itr2-rsu-assistant\.worktrees\implement-plan`

## Global Constraints

- No network calls anywhere in `core/` or `app/` — enforced by existing `test_no_network.py` (pdfplumber is not in the forbidden-module list).
- All uploaded PDFs are written to a temp file, parsed, then deleted — never persisted.
- Missing fields return `confidence="missing"`, value=`None` — never zero-filled.
- Lot-matching for sales is always explicit user input — bulk statement import creates sale events without lot allocations.
- `pdfplumber` is the only new dependency; it is open source (MIT).
- Parser field names must exactly match the v1 form field names: `vest_date`, `shares_vested_gross`, `fmv_per_share_usd`, `shares_withheld_for_tax`, `gross_dividend_usd`, `us_tax_withheld_usd`.

---

## Task 1: pdfplumber + base parser types + Flask session key

**Files:**
- Modify: `requirements.txt`
- Create: `core/parsers/__init__.py`
- Create: `core/parsers/_base.py`
- Modify: `app/routes.py` (add `app.secret_key` — required for Flask session)
- Test: `tests/test_parser_base.py`

**Interfaces:**
- Produces:
  - `ParsedField(value, confidence, source_hint)` dataclass from `core.parsers._base`
  - `ParseResult = dict[str, ParsedField]` type alias from `core.parsers._base`
  - Helper constructors `high(value, hint)`, `medium(value, hint)`, `low(value, hint)`, `missing(field_name)` — all return `ParsedField` — from `core.parsers._base`

- [ ] **Step 1: Install pdfplumber**

Run:
```bash
venv/Scripts/pip.exe install "pdfplumber>=0.11" --index-url https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn
```
Expected: `Successfully installed pdfplumber-...`

- [ ] **Step 2: Update requirements.txt**

Replace the contents of `requirements.txt` with:
```
Flask==3.0.3
pytest==8.2.0
pdfplumber>=0.11
```

- [ ] **Step 3: Create `core/parsers/__init__.py`**

```python
```
(empty file — package marker only)

- [ ] **Step 4: Write the failing test**

`tests/test_parser_base.py`:
```python
from core.parsers._base import ParsedField, ParseResult, high, medium, low, missing


def test_parsedfield_dataclass():
    f = ParsedField(value=123.0, confidence="high", source_hint="label 'Gross Salary'")
    assert f.value == 123.0
    assert f.confidence == "high"
    assert f.source_hint == "label 'Gross Salary'"


def test_helper_high():
    f = high(42.0, "some label")
    assert f.confidence == "high"
    assert f.value == 42.0


def test_helper_medium():
    f = medium(42.0, "some label")
    assert f.confidence == "medium"


def test_helper_low():
    f = low(42.0, "some label")
    assert f.confidence == "low"


def test_helper_missing():
    f = missing("tds_inr")
    assert f.confidence == "missing"
    assert f.value is None
    assert "tds_inr" in f.source_hint


def test_parse_result_is_dict_of_parsedfield():
    result: ParseResult = {
        "gross_salary_inr": high(3500000.0, "hint"),
        "tds_inr": missing("tds_inr"),
    }
    assert result["gross_salary_inr"].value == 3500000.0
    assert result["tds_inr"].confidence == "missing"
```

- [ ] **Step 5: Run test — expect FAIL**

```bash
venv/Scripts/pytest.exe tests/test_parser_base.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.parsers._base'`

- [ ] **Step 6: Create `core/parsers/_base.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

ParseResult = dict[str, "ParsedField"]


@dataclass
class ParsedField:
    value: Any
    confidence: str  # "high" | "medium" | "low" | "missing"
    source_hint: str


def high(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="high", source_hint=hint)


def medium(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="medium", source_hint=hint)


def low(value: Any, hint: str) -> ParsedField:
    return ParsedField(value=value, confidence="low", source_hint=hint)


def missing(field_name: str) -> ParsedField:
    return ParsedField(value=None, confidence="missing", source_hint=f"{field_name} not found")
```

- [ ] **Step 7: Run test — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_base.py -v
```
Expected: `7 passed`

- [ ] **Step 8: Add `app.secret_key` to `app/routes.py`**

Find the line `app = Flask(__name__)` and add the secret key directly below it:

Old:
```python
app = Flask(__name__)
_db_path_holder = {"path": None}
```

New:
```python
app = Flask(__name__)
app.secret_key = "itr2-rsu-dev-secret"
_db_path_holder = {"path": None}
```

- [ ] **Step 9: Run full test suite — all 57 must still pass**

```bash
venv/Scripts/pytest.exe tests/ -q
```
Expected: `57 passed`

- [ ] **Step 10: Commit**

```bash
git add requirements.txt core/parsers/__init__.py core/parsers/_base.py app/routes.py tests/test_parser_base.py
git commit -m "feat: add pdfplumber, base parser types, Flask session key"
```

---

## Task 2: Form 16 and AIS parsers

**Files:**
- Create: `tests/parser_fixtures/form16_sample.txt`
- Create: `tests/parser_fixtures/ais_sample.txt`
- Create: `tests/test_parser_form16.py`
- Create: `tests/test_parser_ais.py`
- Create: `core/parsers/form16.py`
- Create: `core/parsers/ais.py`

**Interfaces:**
- Consumes: `core.parsers._base` (high, medium, missing, ParseResult)
- Produces:
  - `core.parsers.form16.parse(pdf_path: str) -> ParseResult` — keys: `gross_salary_inr`, `rsu_perquisite_value_inr`, `tds_inr`
  - `core.parsers.ais.parse(pdf_path: str) -> ParseResult` — keys: `tds_inr`

- [ ] **Step 1: Create `tests/parser_fixtures/` directory and Form 16 fixture**

Create `tests/parser_fixtures/__init__.py` (empty).

Create `tests/parser_fixtures/form16_sample.txt`:
```
FORM NO. 16
Certificate under section 203 of the Income-tax Act, 1961
for tax deducted at source on salary

Name and address of the Employer: BROADCOM INDIA PRIVATE LIMITED
Name and designation of the Employee: TEST EMPLOYEE
Assessment Year: 2024-25

PART A

SUMMARY OF TAX DEDUCTED AT SOURCE
Total amount of tax deducted and deposited: 350000.00

PART B (Annexure)
Details of Salary Paid and any other income and tax deducted

1. Gross Salary
   (a) Salary as per provisions contained in sec.17(1): 3500000.00
   (b) Value of perquisites u/s 17(2) (as per Form No. 12BA, wherever applicable): 392500.00
   (c) Profits in lieu of salary under section 17(3): 0.00

Total: 3892500.00
```

- [ ] **Step 2: Create AIS fixture**

Create `tests/parser_fixtures/ais_sample.txt`:
```
Annual Information Statement
Assessment Year: 2024-25

SALARY
   Employer Name: BROADCOM INDIA PRIVATE LIMITED
   Amount Paid/Credited: 3892500.00
   Tax Deducted: 350000.00
```

- [ ] **Step 3: Write failing Form 16 test**

`tests/test_parser_form16.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.form16 import parse

FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "form16_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_form16_extracts_gross_salary():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["gross_salary_inr"].confidence == "high"
    assert result["gross_salary_inr"].value == 3500000.0


def test_form16_extracts_perquisite():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["rsu_perquisite_value_inr"].confidence == "high"
    assert result["rsu_perquisite_value_inr"].value == 392500.0


def test_form16_extracts_tds():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "high"
    assert result["tds_inr"].value == 350000.0


def test_form16_missing_fields_return_missing_not_exception():
    with patch("pdfplumber.open", return_value=_mock_pdf("unrecognised content")):
        result = parse("dummy.pdf")
    assert result["gross_salary_inr"].confidence == "missing"
    assert result["gross_salary_inr"].value is None
    assert result["rsu_perquisite_value_inr"].confidence == "missing"
    assert result["tds_inr"].confidence == "missing"
```

- [ ] **Step 4: Run test — expect FAIL**

```bash
venv/Scripts/pytest.exe tests/test_parser_form16.py -v
```
Expected: `ModuleNotFoundError: No module named 'core.parsers.form16'`

- [ ] **Step 5: Create `core/parsers/form16.py`**

```python
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
```

- [ ] **Step 6: Run Form 16 tests — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_form16.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Write failing AIS test**

`tests/test_parser_ais.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.ais import parse

FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "ais_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_ais_extracts_tds():
    text = FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "high"
    assert result["tds_inr"].value == 350000.0


def test_ais_missing_tds_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("no data here")):
        result = parse("dummy.pdf")
    assert result["tds_inr"].confidence == "missing"
    assert result["tds_inr"].value is None
```

- [ ] **Step 8: Create `core/parsers/ais.py`**

```python
import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


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
```

- [ ] **Step 9: Run all parser tests so far**

```bash
venv/Scripts/pytest.exe tests/test_parser_base.py tests/test_parser_form16.py tests/test_parser_ais.py -v
```
Expected: `13 passed`

- [ ] **Step 10: Commit**

```bash
git add tests/parser_fixtures/ tests/test_parser_form16.py tests/test_parser_ais.py core/parsers/form16.py core/parsers/ais.py
git commit -m "feat: add Form 16 and AIS parsers with text-fixture tests"
```

---

## Task 3: Fidelity and Schwab release confirmation parsers

**Files:**
- Create: `tests/parser_fixtures/fidelity_release_sample.txt`
- Create: `tests/parser_fixtures/schwab_release_sample.txt`
- Create: `tests/test_parser_fidelity_release.py`
- Create: `core/parsers/fidelity_release.py`
- Create: `core/parsers/schwab_release.py`

**Interfaces:**
- Consumes: `core.parsers._base`
- Produces:
  - `core.parsers.fidelity_release.parse(pdf_path) -> ParseResult` — keys: `vest_date` (str YYYY-MM-DD), `shares_vested_gross` (float), `fmv_per_share_usd` (float), `shares_withheld_for_tax` (float)
  - `core.parsers.schwab_release.parse(pdf_path) -> ParseResult` — same keys

- [ ] **Step 1: Create Fidelity release fixture**

`tests/parser_fixtures/fidelity_release_sample.txt`:
```
Fidelity Investments
RSU Release Confirmation

Release Date: 10/15/2023
Plan: Restricted Stock Unit Award

Shares Released: 100
Shares Sold for Tax: 30
Net Shares Deposited: 70

Fair Market Value per Share: $785.50
Total Value: $78,550.00
```

- [ ] **Step 2: Create Schwab release fixture**

`tests/parser_fixtures/schwab_release_sample.txt`:
```
Charles Schwab
Equity Award Center
Stock Plan Release Confirmation

Release Date: 04/10/2024
Award Type: Restricted Stock Units

Shares Released: 50
Shares Withheld for Tax: 15
Net Shares Deposited: 35

Fair Market Value at Release: $1,285.75 per share
Total Value at Release: $64,287.50
```

- [ ] **Step 3: Write failing tests**

`tests/test_parser_fidelity_release.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_release import parse as fidelity_parse
from core.parsers.schwab_release import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_release_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_release_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_release_vest_date():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["vest_date"].confidence == "high"
    assert result["vest_date"].value == "2023-10-15"


def test_fidelity_release_shares_vested_gross():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["shares_vested_gross"].value == 100.0
    assert result["shares_vested_gross"].confidence == "high"


def test_fidelity_release_fmv():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["fmv_per_share_usd"].value == 785.50
    assert result["fmv_per_share_usd"].confidence == "high"


def test_fidelity_release_tax_withheld():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["shares_withheld_for_tax"].value == 30.0
    assert result["shares_withheld_for_tax"].confidence == "high"


def test_fidelity_release_missing_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("unrecognised")):
        result = fidelity_parse("dummy.pdf")
    assert all(f.confidence == "missing" for f in result.values())


def test_schwab_release_vest_date():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["vest_date"].value == "2024-04-10"
    assert result["vest_date"].confidence == "high"


def test_schwab_release_shares_vested_gross():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["shares_vested_gross"].value == 50.0


def test_schwab_release_fmv():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["fmv_per_share_usd"].value == 1285.75


def test_schwab_release_tax_withheld():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["shares_withheld_for_tax"].value == 15.0
```

- [ ] **Step 4: Run — expect FAIL**

```bash
venv/Scripts/pytest.exe tests/test_parser_fidelity_release.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 5: Create `core/parsers/fidelity_release.py`**

```python
import re
from datetime import datetime

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {
        "vest_date": _parse_vest_date(text),
        "shares_vested_gross": _parse_shares_released(text),
        "fmv_per_share_usd": _parse_fmv(text),
        "shares_withheld_for_tax": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
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
    m = re.search(
        r"Fair Market Value per Share[:\s]+\$?([\d,]+\.?\d*)", text, re.IGNORECASE
    )
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Fair Market Value per Share'")
    return missing("fmv_per_share_usd")


def _parse_tax_withheld(text: str) -> ParsedField:
    m = re.search(r"Shares Sold for Tax[:\s]+([\d,]+)", text, re.IGNORECASE)
    if m:
        return high(float(m.group(1).replace(",", "")), "label 'Shares Sold for Tax'")
    return missing("shares_withheld_for_tax")
```

- [ ] **Step 6: Create `core/parsers/schwab_release.py`**

```python
import re
from datetime import datetime

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, medium, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {
        "vest_date": _parse_vest_date(text),
        "shares_vested_gross": _parse_shares_released(text),
        "fmv_per_share_usd": _parse_fmv(text),
        "shares_withheld_for_tax": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
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
```

- [ ] **Step 7: Run release tests — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_fidelity_release.py -v
```
Expected: `10 passed`

- [ ] **Step 8: Commit**

```bash
git add tests/parser_fixtures/fidelity_release_sample.txt tests/parser_fixtures/schwab_release_sample.txt tests/test_parser_fidelity_release.py core/parsers/fidelity_release.py core/parsers/schwab_release.py
git commit -m "feat: add Fidelity and Schwab release confirmation parsers"
```

---

## Task 4: Fidelity and Schwab tax form parsers (1042-S / 1099-DIV)

**Files:**
- Create: `tests/parser_fixtures/fidelity_tax_sample.txt`
- Create: `tests/parser_fixtures/schwab_tax_sample.txt`
- Create: `tests/test_parser_tax_forms.py`
- Create: `core/parsers/fidelity_tax.py`
- Create: `core/parsers/schwab_tax.py`

**Interfaces:**
- Produces:
  - `core.parsers.fidelity_tax.parse(pdf_path) -> ParseResult` — keys: `gross_dividend_usd` (float), `us_tax_withheld_usd` (float)
  - `core.parsers.schwab_tax.parse(pdf_path) -> ParseResult` — same keys

- [ ] **Step 1: Create Fidelity tax fixture**

`tests/parser_fixtures/fidelity_tax_sample.txt`:
```
Fidelity Investments
FORM 1042-S
Foreign Person's U.S. Source Income Subject to Withholding
Tax Year: 2023

2. Gross Income: 1250.00
7a. Federal Tax Withheld: 375.00
```

- [ ] **Step 2: Create Schwab tax fixture**

`tests/parser_fixtures/schwab_tax_sample.txt`:
```
Charles Schwab
Form 1099-DIV
Dividends and Distributions
Tax Year: 2023

1a. Total ordinary dividends: $850.00
4. Federal income tax withheld: $0.00
```

- [ ] **Step 3: Write failing tests**

`tests/test_parser_tax_forms.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_tax import parse as fidelity_parse
from core.parsers.schwab_tax import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_tax_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_tax_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_1042s_gross_income():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["gross_dividend_usd"].confidence == "high"
    assert result["gross_dividend_usd"].value == 1250.0


def test_fidelity_1042s_tax_withheld():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert result["us_tax_withheld_usd"].confidence == "high"
    assert result["us_tax_withheld_usd"].value == 375.0


def test_fidelity_tax_missing_returns_missing():
    with patch("pdfplumber.open", return_value=_mock_pdf("nothing here")):
        result = fidelity_parse("dummy.pdf")
    assert all(f.confidence == "missing" for f in result.values())


def test_schwab_1099div_dividend():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["gross_dividend_usd"].confidence == "high"
    assert result["gross_dividend_usd"].value == 850.0


def test_schwab_1099div_tax_withheld():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert result["us_tax_withheld_usd"].confidence == "high"
    assert result["us_tax_withheld_usd"].value == 0.0
```

- [ ] **Step 4: Create `core/parsers/fidelity_tax.py`**

```python
import re

import pdfplumber

from core.parsers._base import ParsedField, ParseResult, high, missing


def parse(pdf_path: str) -> ParseResult:
    text = _extract_text(pdf_path)
    return {
        "gross_dividend_usd": _parse_gross_income(text),
        "us_tax_withheld_usd": _parse_tax_withheld(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
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
```

- [ ] **Step 5: Create `core/parsers/schwab_tax.py`**

```python
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
```

- [ ] **Step 6: Run tax form tests — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_tax_forms.py -v
```
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add tests/parser_fixtures/fidelity_tax_sample.txt tests/parser_fixtures/schwab_tax_sample.txt tests/test_parser_tax_forms.py core/parsers/fidelity_tax.py core/parsers/schwab_tax.py
git commit -m "feat: add Fidelity 1042-S and Schwab 1099-DIV parsers"
```

---

## Task 5: Statement parsers — bulk vesting and sale extraction

**Files:**
- Create: `tests/parser_fixtures/fidelity_statement_sample.txt`
- Create: `tests/parser_fixtures/schwab_statement_sample.txt`
- Create: `tests/test_parser_statements.py`
- Create: `core/parsers/fidelity_statement.py`
- Create: `core/parsers/schwab_statement.py`

**Interfaces:**
- Produces:
  - `core.parsers.fidelity_statement.parse(pdf_path) -> dict` — keys: `"vesting_events": list[dict]`, `"sale_events": list[dict]`
  - Each vesting event dict: `{vest_date: str, shares_vested_gross: float, fmv_per_share_usd: float, shares_withheld_for_tax: float, confidence: str}`
  - Each sale event dict: `{sale_date: str, shares_sold: float, price_per_share_usd: float, confidence: str}`
  - `core.parsers.schwab_statement.parse(pdf_path) -> dict` — same structure

- [ ] **Step 1: Create Fidelity statement fixture**

`tests/parser_fixtures/fidelity_statement_sample.txt`:
```
Fidelity Investments
Account Activity

Date        Transaction Type            Symbol   Qty      Price     Amount
10/15/2023  RSU VEST                   AVGO     100      785.50    78550.00
10/15/2023  TAX WITHHOLDING SELL       AVGO     30       785.50    23565.00
11/20/2023  YOU SOLD                   AVGO     70       810.25    56717.50
```

- [ ] **Step 2: Create Schwab statement fixture**

`tests/parser_fixtures/schwab_statement_sample.txt`:
```
Charles Schwab
Account Activity

Date        Action     Symbol   Qty      Price         Amount
04/10/2024  RS         AVGO     50       1285.75       64287.50
04/10/2024  Tax Wh     AVGO     15       1285.75       19286.25
05/20/2024  Sell       AVGO     35       1350.00       47250.00
```

- [ ] **Step 3: Write failing tests**

`tests/test_parser_statements.py`:
```python
import pathlib
from unittest.mock import MagicMock, patch

from core.parsers.fidelity_statement import parse as fidelity_parse
from core.parsers.schwab_statement import parse as schwab_parse

FID_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "fidelity_statement_sample.txt"
SCH_FIXTURE = pathlib.Path(__file__).parent / "parser_fixtures" / "schwab_statement_sample.txt"


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_fidelity_statement_extracts_vesting_event():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert len(result["vesting_events"]) == 1
    v = result["vesting_events"][0]
    assert v["vest_date"] == "2023-10-15"
    assert v["shares_vested_gross"] == 100.0
    assert v["fmv_per_share_usd"] == 785.50
    assert v["shares_withheld_for_tax"] == 30.0


def test_fidelity_statement_extracts_sale_event():
    text = FID_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = fidelity_parse("dummy.pdf")
    assert len(result["sale_events"]) == 1
    s = result["sale_events"][0]
    assert s["sale_date"] == "2023-11-20"
    assert s["shares_sold"] == 70.0
    assert s["price_per_share_usd"] == 810.25


def test_fidelity_statement_empty_text_returns_empty_lists():
    with patch("pdfplumber.open", return_value=_mock_pdf("nothing here")):
        result = fidelity_parse("dummy.pdf")
    assert result["vesting_events"] == []
    assert result["sale_events"] == []


def test_schwab_statement_extracts_vesting_event():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert len(result["vesting_events"]) == 1
    v = result["vesting_events"][0]
    assert v["vest_date"] == "2024-04-10"
    assert v["shares_vested_gross"] == 50.0
    assert v["fmv_per_share_usd"] == 1285.75
    assert v["shares_withheld_for_tax"] == 15.0


def test_schwab_statement_extracts_sale_event():
    text = SCH_FIXTURE.read_text(encoding="utf-8")
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        result = schwab_parse("dummy.pdf")
    assert len(result["sale_events"]) == 1
    s = result["sale_events"][0]
    assert s["sale_date"] == "2024-05-20"
    assert s["shares_sold"] == 35.0
    assert s["price_per_share_usd"] == 1350.0
```

- [ ] **Step 4: Create `core/parsers/fidelity_statement.py`**

```python
import re
from datetime import datetime

import pdfplumber


def parse(pdf_path: str) -> dict:
    text = _extract_text(pdf_path)
    return {
        "vesting_events": _parse_vesting_events(text),
        "sale_events": _parse_sale_events(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
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
```

- [ ] **Step 5: Create `core/parsers/schwab_statement.py`**

```python
import re
from datetime import datetime

import pdfplumber


def parse(pdf_path: str) -> dict:
    text = _extract_text(pdf_path)
    return {
        "vesting_events": _parse_vesting_events(text),
        "sale_events": _parse_sale_events(text),
    }


def _extract_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_vesting_events(text: str) -> list:
    events = []
    vest_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+RS\s+\w+\s+([\d,]+)\s+([\d,]+\.?\d*)", re.IGNORECASE
    )
    for m in vest_pattern.finditer(text):
        vest_date = datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        shares = float(m.group(2).replace(",", ""))
        fmv = float(m.group(3).replace(",", ""))
        tax_pattern = re.compile(
            rf"{re.escape(m.group(1))}\s+Tax Wh\s+\w+\s+([\d,]+)", re.IGNORECASE
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
        r"(\d{2}/\d{2}/\d{4})\s+Sell\s+\w+\s+([\d,]+)\s+([\d,]+\.?\d*)", re.IGNORECASE
    )
    for m in pattern.finditer(text):
        events.append({
            "sale_date": datetime.strptime(m.group(1), "%m/%d/%Y").strftime("%Y-%m-%d"),
            "shares_sold": float(m.group(2).replace(",", "")),
            "price_per_share_usd": float(m.group(3).replace(",", "")),
            "confidence": "high",
        })
    return events
```

- [ ] **Step 6: Run statement tests — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_statements.py -v
```
Expected: `8 passed`

- [ ] **Step 7: Commit**

```bash
git add tests/parser_fixtures/fidelity_statement_sample.txt tests/parser_fixtures/schwab_statement_sample.txt tests/test_parser_statements.py core/parsers/fidelity_statement.py core/parsers/schwab_statement.py
git commit -m "feat: add Fidelity and Schwab statement parsers (bulk vesting + sales)"
```

---

## Task 6: Document type detection

**Files:**
- Create: `core/parsers/detect.py`
- Create: `tests/test_parser_detect.py`

**Interfaces:**
- Produces: `core.parsers.detect.detect_document_type(pdf_path: str) -> str`
  Returns one of: `"form16"`, `"ais"`, `"fidelity_release"`, `"fidelity_tax"`, `"fidelity_statement"`, `"schwab_release"`, `"schwab_tax"`, `"schwab_statement"`, `"unknown"`

- [ ] **Step 1: Write failing test**

`tests/test_parser_detect.py`:
```python
from unittest.mock import MagicMock, patch

from core.parsers.detect import detect_document_type


def _mock_pdf(text: str):
    page = MagicMock()
    page.extract_text.return_value = text
    pdf = MagicMock()
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    pdf.pages = [page]
    return pdf


def test_detects_form16():
    text = "FORM NO. 16\nCertificate under section 203 of the Income-tax Act"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "form16"


def test_detects_ais():
    text = "Annual Information Statement\nAssessment Year: 2024-25"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "ais"


def test_detects_fidelity_release():
    text = "Fidelity Investments\nRSU Release Confirmation\nRelease Date: 10/15/2023"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_release"


def test_detects_fidelity_tax():
    text = "Fidelity Investments\nFORM 1042-S\nGross Income: 1250.00"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_tax"


def test_detects_fidelity_statement():
    text = "Fidelity Investments\nAccount Activity\nTransaction Type\nRSU VEST"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "fidelity_statement"


def test_detects_schwab_release():
    text = "Charles Schwab\nStock Plan Release Confirmation\nRelease Date: 04/10/2024"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_release"


def test_detects_schwab_tax():
    text = "Charles Schwab\nForm 1099-DIV\nTotal ordinary dividends"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_tax"


def test_detects_schwab_statement():
    text = "Charles Schwab\nAccount Activity\nRS\nSell\nTax Wh"
    with patch("pdfplumber.open", return_value=_mock_pdf(text)):
        assert detect_document_type("dummy.pdf") == "schwab_statement"


def test_unknown_document_returns_unknown():
    with patch("pdfplumber.open", return_value=_mock_pdf("random unrelated text")):
        assert detect_document_type("dummy.pdf") == "unknown"
```

- [ ] **Step 2: Run — expect FAIL**

```bash
venv/Scripts/pytest.exe tests/test_parser_detect.py -v
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `core/parsers/detect.py`**

```python
import pdfplumber

# Each entry: (doc_type, required_phrases_in_first_page)
# Ordered most-specific first to avoid false positives.
_SIGNATURES = [
    ("fidelity_release", ["Fidelity Investments", "Release Confirmation"]),
    ("fidelity_tax",     ["Fidelity Investments", "1042-S"]),
    ("fidelity_tax",     ["Fidelity Investments", "1099-DIV"]),
    ("fidelity_statement", ["Fidelity Investments", "Account Activity"]),
    ("schwab_release",   ["Charles Schwab", "Release Confirmation"]),
    ("schwab_tax",       ["Charles Schwab", "1099-DIV"]),
    ("schwab_tax",       ["Charles Schwab", "1042-S"]),
    ("schwab_statement", ["Charles Schwab", "Account Activity"]),
    ("form16",           ["FORM NO. 16"]),
    ("form16",           ["Form No. 16"]),
    ("ais",              ["Annual Information Statement"]),
]


def detect_document_type(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""
    for doc_type, phrases in _SIGNATURES:
        if all(phrase in first_page_text for phrase in phrases):
            return doc_type
    return "unknown"
```

- [ ] **Step 4: Run — expect PASS**

```bash
venv/Scripts/pytest.exe tests/test_parser_detect.py -v
```
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add core/parsers/detect.py tests/test_parser_detect.py
git commit -m "feat: add document type detection for all 8 PDF sources"
```

---

## Task 7: Upload routes

**Files:**
- Modify: `app/routes.py`

**Interfaces:**
- Consumes: `core.parsers.detect.detect_document_type`, all 8 parser modules
- Produces (new routes):
  - `POST /year/<ay_label>/form16/upload` — handles Form 16 and AIS; stores result in `session["form16_prefill"]` or `session["ais_prefill"]`
  - `POST /year/<ay_label>/vesting/upload` — handles Fidelity/Schwab release confirmation; stores in `session["vesting_prefill"]`
  - `POST /year/<ay_label>/vesting/upload-bulk` — handles Fidelity/Schwab statement; stores in `session["vesting_bulk_prefill"]`
  - `POST /year/<ay_label>/sales/upload-bulk` — handles Fidelity/Schwab statement; stores in `session["sales_bulk_prefill"]`
  - `POST /year/<ay_label>/dividends/upload` — handles Fidelity/Schwab tax form; stores in `session["dividends_prefill"]`
- Modifies existing routes to read and clear session prefill on GET:
  - `form16_entry` GET: reads and pops `session["form16_prefill"]` and `session["ais_prefill"]`; passes to template
  - `vesting_entry` GET: reads and pops `session["vesting_prefill"]`; reads (no pop) `session["vesting_bulk_prefill"]`; passes both to template
  - `vesting_entry` POST: adds `action=save_bulk` branch that reads `session["vesting_bulk_prefill"]` and saves checked rows
  - `sale_entry` GET: reads (no pop) `session["sales_bulk_prefill"]`; passes to template
  - `sale_entry` POST: adds `action=save_bulk` branch
  - `dividend_entry` GET: reads and pops `session["dividends_prefill"]`; passes to template

- [ ] **Step 1: Add imports and upload helper to `app/routes.py`**

Add at the top of `app/routes.py` (after existing imports):
```python
import os
import tempfile

from flask import Flask, flash, redirect, render_template, request, session, url_for
```

Replace the existing Flask import line:
```python
from flask import Flask, redirect, render_template, request, url_for
```
with:
```python
import os
import tempfile

from flask import Flask, flash, redirect, render_template, request, session, url_for
```

Add this helper function after `get_db()`:
```python
def _save_upload_to_temp(file_storage) -> str:
    """Save an uploaded FileStorage to a temp file and return the path."""
    suffix = os.path.splitext(file_storage.filename or "upload.pdf")[1] or ".pdf"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    file_storage.save(path)
    return path
```

- [ ] **Step 2: Add Form 16 / AIS upload route to `app/routes.py`**

Add after the existing `form16_entry` route:
```python
@app.route("/year/<ay_label>/form16/upload", methods=["POST"])
def form16_upload(ay_label: str):
    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("No file uploaded.")
        return redirect(url_for("form16_entry", ay_label=ay_label))
    tmp_path = _save_upload_to_temp(f)
    try:
        from core.parsers.detect import detect_document_type
        doc_type = detect_document_type(tmp_path)
        if doc_type == "form16":
            from core.parsers.form16 import parse
            result = parse(tmp_path)
            session["form16_prefill"] = {
                k: {"value": v.value, "confidence": v.confidence, "hint": v.source_hint}
                for k, v in result.items()
            }
        elif doc_type == "ais":
            from core.parsers.ais import parse
            result = parse(tmp_path)
            session["ais_prefill"] = {
                k: {"value": v.value, "confidence": v.confidence, "hint": v.source_hint}
                for k, v in result.items()
            }
        else:
            flash(f"Unrecognised document type '{doc_type}'. Expected Form 16 or AIS PDF.")
    finally:
        os.unlink(tmp_path)
    return redirect(url_for("form16_entry", ay_label=ay_label))
```

- [ ] **Step 3: Modify `form16_entry` to read session prefill on GET**

Replace the existing `form16_entry` route body's GET path:

Old return statement at the bottom:
```python
    form16 = db.get_form16_summary(ay_id)
    return render_template("form16_entry.html", ay_label=ay_label, form16=form16)
```

New:
```python
    form16 = db.get_form16_summary(ay_id)
    form16_prefill = session.pop("form16_prefill", None)
    ais_prefill = session.pop("ais_prefill", None)
    return render_template(
        "form16_entry.html",
        ay_label=ay_label,
        form16=form16,
        form16_prefill=form16_prefill,
        ais_prefill=ais_prefill,
    )
```

- [ ] **Step 4: Add vesting upload routes**

Add after the existing `vesting_entry` route:
```python
@app.route("/year/<ay_label>/vesting/upload", methods=["POST"])
def vesting_upload(ay_label: str):
    """Single release confirmation — pre-fills the add-vesting form."""
    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("No file uploaded.")
        return redirect(url_for("vesting_entry", ay_label=ay_label))
    tmp_path = _save_upload_to_temp(f)
    try:
        from core.parsers.detect import detect_document_type
        doc_type = detect_document_type(tmp_path)
        if doc_type == "fidelity_release":
            from core.parsers.fidelity_release import parse
        elif doc_type == "schwab_release":
            from core.parsers.schwab_release import parse
        else:
            flash(f"Expected a Fidelity or Schwab RSU Release Confirmation PDF, got '{doc_type}'.")
            return redirect(url_for("vesting_entry", ay_label=ay_label))
        result = parse(tmp_path)
        session["vesting_prefill"] = {
            k: {"value": v.value, "confidence": v.confidence, "hint": v.source_hint}
            for k, v in result.items()
        }
    finally:
        os.unlink(tmp_path)
    return redirect(url_for("vesting_entry", ay_label=ay_label))


@app.route("/year/<ay_label>/vesting/upload-bulk", methods=["POST"])
def vesting_upload_bulk(ay_label: str):
    """Transaction history — bulk vesting event review."""
    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("No file uploaded.")
        return redirect(url_for("vesting_entry", ay_label=ay_label))
    tmp_path = _save_upload_to_temp(f)
    try:
        from core.parsers.detect import detect_document_type
        doc_type = detect_document_type(tmp_path)
        if doc_type == "fidelity_statement":
            from core.parsers.fidelity_statement import parse
        elif doc_type == "schwab_statement":
            from core.parsers.schwab_statement import parse
        else:
            flash(f"Expected a Fidelity or Schwab transaction history PDF, got '{doc_type}'.")
            return redirect(url_for("vesting_entry", ay_label=ay_label))
        result = parse(tmp_path)
        session["vesting_bulk_prefill"] = result["vesting_events"]
    finally:
        os.unlink(tmp_path)
    return redirect(url_for("vesting_entry", ay_label=ay_label))
```

- [ ] **Step 5: Modify `vesting_entry` to read session prefill and handle bulk save**

Replace the entire `vesting_entry` function with:
```python
@app.route("/year/<ay_label>/vesting", methods=["GET", "POST"])
def vesting_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())

    if request.method == "POST":
        action = request.form.get("action", "add_single")
        if action == "save_bulk":
            bulk_events = session.pop("vesting_bulk_prefill", [])
            selected = set(request.form.getlist("selected_rows"))
            for i, ev in enumerate(bulk_events):
                if str(i) in selected:
                    db.save_vesting_event(
                        ay_id,
                        vest_date=date.fromisoformat(ev["vest_date"]),
                        shares_vested_gross=float(ev["shares_vested_gross"]),
                        fmv_per_share_usd=float(ev["fmv_per_share_usd"]),
                        shares_withheld_for_tax=float(ev["shares_withheld_for_tax"]),
                    )
        else:
            db.save_vesting_event(
                ay_id,
                vest_date=date.fromisoformat(request.form["vest_date"]),
                shares_vested_gross=float(request.form["shares_vested_gross"]),
                fmv_per_share_usd=float(request.form["fmv_per_share_usd"]),
                shares_withheld_for_tax=float(request.form["shares_withheld_for_tax"]),
            )
        return redirect(url_for("vesting_entry", ay_label=ay_label))

    vesting_events = db.list_vesting_events(ay_id)
    vesting_prefill = session.pop("vesting_prefill", None)
    vesting_bulk = session.get("vesting_bulk_prefill")  # kept until bulk-save POST
    return render_template(
        "vesting_entry.html",
        ay_label=ay_label,
        vesting_events=vesting_events,
        vesting_prefill=vesting_prefill,
        vesting_bulk=vesting_bulk,
    )
```

- [ ] **Step 6: Add sales bulk upload route and modify `sale_entry`**

Add after the existing `sale_entry` route:
```python
@app.route("/year/<ay_label>/sales/upload-bulk", methods=["POST"])
def sales_upload_bulk(ay_label: str):
    """Transaction history — bulk sale event review. No lot allocations on upload."""
    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("No file uploaded.")
        return redirect(url_for("sale_entry", ay_label=ay_label))
    tmp_path = _save_upload_to_temp(f)
    try:
        from core.parsers.detect import detect_document_type
        doc_type = detect_document_type(tmp_path)
        if doc_type == "fidelity_statement":
            from core.parsers.fidelity_statement import parse
        elif doc_type == "schwab_statement":
            from core.parsers.schwab_statement import parse
        else:
            flash(f"Expected a Fidelity or Schwab transaction history PDF, got '{doc_type}'.")
            return redirect(url_for("sale_entry", ay_label=ay_label))
        result = parse(tmp_path)
        session["sales_bulk_prefill"] = result["sale_events"]
    finally:
        os.unlink(tmp_path)
    return redirect(url_for("sale_entry", ay_label=ay_label))
```

Modify `sale_entry` to handle bulk save. Replace the entire `sale_entry` function with:
```python
@app.route("/year/<ay_label>/sales", methods=["GET", "POST"])
def sale_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    vesting_events = db.list_vesting_events(ay_id)

    if request.method == "POST":
        action = request.form.get("action", "add_single")
        if action == "save_bulk":
            bulk_events = session.pop("sales_bulk_prefill", [])
            selected = set(request.form.getlist("selected_rows"))
            for i, ev in enumerate(bulk_events):
                if str(i) in selected:
                    db.save_sale_event(
                        ay_id,
                        date.fromisoformat(ev["sale_date"]),
                        float(ev["shares_sold"]),
                        float(ev["price_per_share_usd"]),
                    )
            # No lot allocations on bulk import — user adds them manually.
        else:
            sale_date = date.fromisoformat(request.form["sale_date"])
            quantity_sold = float(request.form["quantity_sold"])
            sale_price_per_share_usd = float(request.form["sale_price_per_share_usd"])
            sale_id = db.save_sale_event(ay_id, sale_date, quantity_sold, sale_price_per_share_usd)
            allocations = []
            for v in vesting_events:
                qty_key = f"lot_qty_{v.id}"
                qty = float(request.form.get(qty_key, 0) or 0)
                if qty > 0:
                    allocations.append((v.id, qty))
            db.save_sale_lot_allocations(sale_id, allocations)
        return redirect(url_for("sale_entry", ay_label=ay_label))

    sales_with_allocations = db.list_sale_events_with_allocations(ay_id)
    sale_events = [s for s, _ in sales_with_allocations]
    sales_bulk = session.get("sales_bulk_prefill")
    return render_template(
        "sale_entry.html",
        ay_label=ay_label,
        vesting_events=vesting_events,
        sale_events=sale_events,
        sales_bulk=sales_bulk,
    )
```

- [ ] **Step 7: Add dividends upload route and modify `dividend_entry`**

Add after the existing `dividend_entry` route:
```python
@app.route("/year/<ay_label>/dividends/upload", methods=["POST"])
def dividends_upload(ay_label: str):
    f = request.files.get("pdf")
    if not f or not f.filename:
        flash("No file uploaded.")
        return redirect(url_for("dividend_entry", ay_label=ay_label))
    tmp_path = _save_upload_to_temp(f)
    try:
        from core.parsers.detect import detect_document_type
        doc_type = detect_document_type(tmp_path)
        if doc_type == "fidelity_tax":
            from core.parsers.fidelity_tax import parse
        elif doc_type == "schwab_tax":
            from core.parsers.schwab_tax import parse
        else:
            flash(f"Expected a 1042-S or 1099-DIV PDF, got '{doc_type}'.")
            return redirect(url_for("dividend_entry", ay_label=ay_label))
        result = parse(tmp_path)
        session["dividends_prefill"] = {
            k: {"value": v.value, "confidence": v.confidence, "hint": v.source_hint}
            for k, v in result.items()
        }
    finally:
        os.unlink(tmp_path)
    return redirect(url_for("dividend_entry", ay_label=ay_label))
```

Modify `dividend_entry` GET return:

Old:
```python
    dividend_events = db.list_dividend_events(ay_id)
    return render_template("dividend_entry.html", ay_label=ay_label, dividend_events=dividend_events)
```

New:
```python
    dividend_events = db.list_dividend_events(ay_id)
    dividends_prefill = session.pop("dividends_prefill", None)
    return render_template(
        "dividend_entry.html",
        ay_label=ay_label,
        dividend_events=dividend_events,
        dividends_prefill=dividends_prefill,
    )
```

- [ ] **Step 8: Run full test suite — all 57 must still pass**

```bash
venv/Scripts/pytest.exe tests/ -q
```
Expected: `57 passed`

- [ ] **Step 9: Commit**

```bash
git add app/routes.py
git commit -m "feat: add PDF upload routes with session-based prefill for all entry pages"
```

---

## Task 8: Template updates — confidence badges and bulk review tables

**Files:**
- Modify: `app/templates/form16_entry.html`
- Modify: `app/templates/vesting_entry.html`
- Modify: `app/templates/sale_entry.html`
- Modify: `app/templates/dividend_entry.html`
- Modify: `app/templates/base.html` (add confidence badge CSS)

**Interfaces:**
- Consumes: session prefill dicts passed from routes as template variables `form16_prefill`, `ais_prefill`, `vesting_prefill`, `vesting_bulk`, `sales_bulk`, `dividends_prefill`

- [ ] **Step 1: Add confidence badge CSS to `base.html`**

Read `app/templates/base.html`. Find the `<style>` block and add inside it, before the closing `</style>`:

```css
    .upload-section { margin: 1rem 0; padding: 0.75rem; background: #f5f5f5; border-radius: 4px; }
    .upload-section h3 { margin-top: 0; font-size: 1rem; }
    .badge { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-left: 4px; vertical-align: middle; }
    .badge-high { background: #2e7d32; }
    .badge-medium { background: #f57c00; }
    .badge-low { background: #e65100; }
    .badge-missing { background: #c62828; }
    .prefill-hint { font-size: 0.75rem; color: #666; margin-left: 4px; }
    .bulk-review { margin: 1.5rem 0; }
    .bulk-review table { width: 100%; }
    .flash-messages { background: #fff3cd; padding: 0.5rem 1rem; border-left: 4px solid #ffc107; margin-bottom: 1rem; }
```

Also add flash message rendering to base.html. Find the `<body>` tag content area and add just after `{% block content %}` opens — actually add it right before `{% block content %}` in the body:

Find:
```html
  {% block content %}{% endblock %}
```

Replace with:
```html
  {% with messages = get_flashed_messages() %}
  {% if messages %}
  <div class="flash-messages">{% for m in messages %}<p>{{ m }}</p>{% endfor %}</div>
  {% endif %}
  {% endwith %}
  {% block content %}{% endblock %}
```

- [ ] **Step 2: Replace `form16_entry.html`**

Full new content of `app/templates/form16_entry.html`:
```html
{% extends "base.html" %}
{% block content %}
  <h1>Form 16 — {{ ay_label }}</h1>

  <div class="upload-section">
    <h3>Auto-fill from PDF</h3>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('form16_upload', ay_label=ay_label) }}">
      <label>Upload Form 16 or AIS PDF:</label>
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">Parse PDF</button>
    </form>
  </div>

  {% if ais_prefill %}
  <div class="upload-section" style="background:#e8f5e9;">
    <strong>AIS cross-check — TDS:</strong>
    {{ ais_prefill.tds_inr.value }}
    <span class="badge badge-{{ ais_prefill.tds_inr.confidence }}" title="{{ ais_prefill.tds_inr.hint }}"></span>
    {% if form16_prefill and form16_prefill.tds_inr.value != ais_prefill.tds_inr.value %}
    <span style="color:#b71c1c;"> ⚠ Differs from Form 16 value ({{ form16_prefill.tds_inr.value }}). Verify before saving.</span>
    {% endif %}
  </div>
  {% endif %}

  <form method="post">
    <label for="gross_salary_inr">Gross Salary (INR)
      {% if form16_prefill %}<span class="badge badge-{{ form16_prefill.gross_salary_inr.confidence }}" title="{{ form16_prefill.gross_salary_inr.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.01" id="gross_salary_inr" name="gross_salary_inr"
           value="{{ form16_prefill.gross_salary_inr.value if form16_prefill and form16_prefill.gross_salary_inr.value is not none else (form16.gross_salary_inr if form16 else '') }}" required>
    <div class="field-help">Form 16 Part B, "Details of Salary Paid" section.</div>

    <label for="rsu_perquisite_value_inr">RSU Perquisite Value (INR)
      {% if form16_prefill %}<span class="badge badge-{{ form16_prefill.rsu_perquisite_value_inr.confidence }}" title="{{ form16_prefill.rsu_perquisite_value_inr.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.01" id="rsu_perquisite_value_inr" name="rsu_perquisite_value_inr"
           value="{{ form16_prefill.rsu_perquisite_value_inr.value if form16_prefill and form16_prefill.rsu_perquisite_value_inr.value is not none else (form16.rsu_perquisite_value_inr if form16 else '') }}" required>
    <div class="field-help">Form 16 Part B, under "Value of perquisites u/s 17(2)".</div>

    <label for="tds_inr">TDS — Tax Deducted at Source (INR)
      {% if form16_prefill %}<span class="badge badge-{{ form16_prefill.tds_inr.confidence }}" title="{{ form16_prefill.tds_inr.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.01" id="tds_inr" name="tds_inr"
           value="{{ form16_prefill.tds_inr.value if form16_prefill and form16_prefill.tds_inr.value is not none else (form16.tds_inr if form16 else '') }}" required>
    <div class="field-help">Form 16 Part A, "Total tax deducted".</div>

    <button type="submit" style="margin-top: 1rem;">Save</button>
  </form>
{% endblock %}
```

- [ ] **Step 3: Replace `vesting_entry.html`**

Full new content of `app/templates/vesting_entry.html`:
```html
{% extends "base.html" %}
{% block content %}
  <h1>RSU Vesting Events — {{ ay_label }}</h1>

  <div class="upload-section">
    <h3>Auto-fill from Release Confirmation PDF</h3>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('vesting_upload', ay_label=ay_label) }}">
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">Parse Release Confirmation</button>
    </form>
  </div>

  <div class="upload-section">
    <h3>Bulk import from Transaction History PDF</h3>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('vesting_upload_bulk', ay_label=ay_label) }}">
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">Parse Transaction History</button>
    </form>
  </div>

  {% if vesting_bulk %}
  <div class="bulk-review">
    <h3>Review extracted vesting events — uncheck any to skip</h3>
    <form method="post">
      <input type="hidden" name="action" value="save_bulk">
      <table>
        <tr><th>Save?</th><th>Vest Date</th><th>Shares Vested</th><th>FMV/Share (USD)</th><th>Shares Withheld</th><th>Confidence</th></tr>
        {% for i, ev in vesting_bulk | enumerate %}
        <tr>
          <td><input type="checkbox" name="selected_rows" value="{{ i }}" checked></td>
          <td>{{ ev.vest_date }}</td>
          <td>{{ ev.shares_vested_gross }}</td>
          <td>{{ ev.fmv_per_share_usd }}</td>
          <td>{{ ev.shares_withheld_for_tax }}</td>
          <td><span class="badge badge-{{ ev.confidence }}"></span> {{ ev.confidence }}</td>
        </tr>
        {% endfor %}
      </table>
      <button type="submit" style="margin-top:0.5rem;">Save selected</button>
    </form>
  </div>
  {% endif %}

  <hr>
  <h3>Add vesting event manually</h3>
  <form method="post">
    <input type="hidden" name="action" value="add_single">
    <label for="vest_date">Vest date
      {% if vesting_prefill %}<span class="badge badge-{{ vesting_prefill.vest_date.confidence }}" title="{{ vesting_prefill.vest_date.hint }}"></span>{% endif %}
    </label>
    <input type="date" id="vest_date" name="vest_date"
           value="{{ vesting_prefill.vest_date.value if vesting_prefill and vesting_prefill.vest_date.value is not none else '' }}" required>
    <div class="field-help">Schwab "Release Confirmation" or Fidelity release statement — "Vest Date" / "Release Date".</div>

    <label for="shares_vested_gross">Shares vested (gross)
      {% if vesting_prefill %}<span class="badge badge-{{ vesting_prefill.shares_vested_gross.confidence }}" title="{{ vesting_prefill.shares_vested_gross.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.0001" id="shares_vested_gross" name="shares_vested_gross"
           value="{{ vesting_prefill.shares_vested_gross.value if vesting_prefill and vesting_prefill.shares_vested_gross.value is not none else '' }}" required>
    <div class="field-help">Same statement — "Shares Released" / "Gross Shares".</div>

    <label for="fmv_per_share_usd">FMV per share at vest (USD)
      {% if vesting_prefill %}<span class="badge badge-{{ vesting_prefill.fmv_per_share_usd.confidence }}" title="{{ vesting_prefill.fmv_per_share_usd.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.0001" id="fmv_per_share_usd" name="fmv_per_share_usd"
           value="{{ vesting_prefill.fmv_per_share_usd.value if vesting_prefill and vesting_prefill.fmv_per_share_usd.value is not none else '' }}" required>
    <div class="field-help">Same statement — "Fair Market Value" / "FMV per Share".</div>

    <label for="shares_withheld_for_tax">Shares withheld for tax
      {% if vesting_prefill %}<span class="badge badge-{{ vesting_prefill.shares_withheld_for_tax.confidence }}" title="{{ vesting_prefill.shares_withheld_for_tax.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.0001" id="shares_withheld_for_tax" name="shares_withheld_for_tax"
           value="{{ vesting_prefill.shares_withheld_for_tax.value if vesting_prefill and vesting_prefill.shares_withheld_for_tax.value is not none else '' }}" required>
    <div class="field-help">Same statement — "Shares Withheld for Taxes" / "Shares Sold to Cover Taxes".</div>

    <button type="submit" style="margin-top: 1rem;">Add Vesting Event</button>
  </form>

  <table>
    <tr><th>Vest Date</th><th>Shares Vested</th><th>FMV/Share (USD)</th><th>Shares Withheld</th></tr>
    {% for v in vesting_events %}
    <tr>
      <td>{{ v.vest_date }}</td>
      <td>{{ v.shares_vested_gross }}</td>
      <td>{{ v.fmv_per_share_usd }}</td>
      <td>{{ v.shares_withheld_for_tax }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

**Note:** The `| enumerate` filter is not built into Jinja2. Add it to the Flask app in `app/routes.py`:

After `app.secret_key = "itr2-rsu-dev-secret"` add:
```python
app.jinja_env.filters["enumerate"] = enumerate
```

- [ ] **Step 4: Replace `sale_entry.html`**

Read `app/templates/sale_entry.html`. Add the bulk upload section and bulk review table at the top of the content block, before the existing manual-add form. Replace the entire file with:

```html
{% extends "base.html" %}
{% block content %}
  <h1>Sale Events — {{ ay_label }}</h1>

  <div class="upload-section">
    <h3>Bulk import from Transaction History PDF</h3>
    <p class="field-help">Sale events are imported without lot allocations — assign lots manually after import.</p>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('sales_upload_bulk', ay_label=ay_label) }}">
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">Parse Transaction History</button>
    </form>
  </div>

  {% if sales_bulk %}
  <div class="bulk-review">
    <h3>Review extracted sale events — uncheck any to skip</h3>
    <form method="post">
      <input type="hidden" name="action" value="save_bulk">
      <table>
        <tr><th>Save?</th><th>Sale Date</th><th>Shares Sold</th><th>Price/Share (USD)</th><th>Confidence</th></tr>
        {% for i, ev in sales_bulk | enumerate %}
        <tr>
          <td><input type="checkbox" name="selected_rows" value="{{ i }}" checked></td>
          <td>{{ ev.sale_date }}</td>
          <td>{{ ev.shares_sold }}</td>
          <td>{{ ev.price_per_share_usd }}</td>
          <td><span class="badge badge-{{ ev.confidence }}"></span> {{ ev.confidence }}</td>
        </tr>
        {% endfor %}
      </table>
      <button type="submit" style="margin-top:0.5rem;">Save selected (no lot allocation)</button>
    </form>
  </div>
  {% endif %}

  <hr>
  <h3>Add sale event manually</h3>
  <form method="post">
    <input type="hidden" name="action" value="add_single">
    <label for="sale_date">Sale date</label>
    <input type="date" id="sale_date" name="sale_date" required>

    <label for="quantity_sold">Quantity sold</label>
    <input type="number" step="0.0001" id="quantity_sold" name="quantity_sold" required>

    <label for="sale_price_per_share_usd">Sale price per share (USD)</label>
    <input type="number" step="0.0001" id="sale_price_per_share_usd" name="sale_price_per_share_usd" required>

    <h4>Lot allocation (which vesting lots do these shares come from?)</h4>
    <div class="field-help">Enter the number of shares from each vesting lot. Total must equal quantity sold.</div>
    {% for v in vesting_events %}
    <label>Vest {{ v.vest_date }} — {{ v.shares_vested_gross }} shares @ ${{ v.fmv_per_share_usd }}</label>
    <input type="number" step="0.0001" name="lot_qty_{{ v.id }}" value="0" min="0">
    {% endfor %}

    <button type="submit" style="margin-top: 1rem;">Add Sale Event</button>
  </form>

  <table>
    <tr><th>Sale Date</th><th>Qty Sold</th><th>Price/Share (USD)</th></tr>
    {% for s in sale_events %}
    <tr>
      <td>{{ s.sale_date }}</td>
      <td>{{ s.quantity_sold }}</td>
      <td>{{ s.sale_price_per_share_usd }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 5: Replace `dividend_entry.html`**

Full new content of `app/templates/dividend_entry.html`:
```html
{% extends "base.html" %}
{% block content %}
  <h1>Dividend Events — {{ ay_label }}</h1>

  <div class="upload-section">
    <h3>Auto-fill from 1042-S or 1099-DIV PDF</h3>
    <form method="post" enctype="multipart/form-data" action="{{ url_for('dividends_upload', ay_label=ay_label) }}">
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">Parse Tax Form</button>
    </form>
  </div>

  <form method="post">
    <label for="payment_date">Dividend payment date</label>
    <input type="date" id="payment_date" name="payment_date" required>
    <div class="field-help">1042-S or 1099-DIV, or brokerage dividend statement — "Payment Date".</div>

    <label for="gross_dividend_usd">Gross dividend (USD)
      {% if dividends_prefill %}<span class="badge badge-{{ dividends_prefill.gross_dividend_usd.confidence }}" title="{{ dividends_prefill.gross_dividend_usd.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.0001" id="gross_dividend_usd" name="gross_dividend_usd"
           value="{{ dividends_prefill.gross_dividend_usd.value if dividends_prefill and dividends_prefill.gross_dividend_usd.value is not none else '' }}" required>
    <div class="field-help">1042-S Box 2 ("Gross Income") or 1099-DIV Box 1a.</div>

    <label for="us_tax_withheld_usd">US tax withheld (USD)
      {% if dividends_prefill %}<span class="badge badge-{{ dividends_prefill.us_tax_withheld_usd.confidence }}" title="{{ dividends_prefill.us_tax_withheld_usd.hint }}"></span>{% endif %}
    </label>
    <input type="number" step="0.0001" id="us_tax_withheld_usd" name="us_tax_withheld_usd"
           value="{{ dividends_prefill.us_tax_withheld_usd.value if dividends_prefill and dividends_prefill.us_tax_withheld_usd.value is not none else '' }}" required>
    <div class="field-help">1042-S Box 7a ("Federal tax withheld") or 1099-DIV Box 4.</div>

    <button type="submit" style="margin-top: 1rem;">Add Dividend</button>
  </form>

  <table>
    <tr><th>Payment Date</th><th>Gross Dividend (USD)</th><th>US Tax Withheld (USD)</th></tr>
    {% for d in dividend_events %}
    <tr>
      <td>{{ d.payment_date }}</td>
      <td>{{ d.gross_dividend_usd }}</td>
      <td>{{ d.us_tax_withheld_usd }}</td>
    </tr>
    {% endfor %}
  </table>
{% endblock %}
```

- [ ] **Step 6: Run full test suite — all 57 must still pass**

```bash
venv/Scripts/pytest.exe tests/ -q
```
Expected: `57 passed`

- [ ] **Step 7: Commit**

```bash
git add app/templates/base.html app/templates/form16_entry.html app/templates/vesting_entry.html app/templates/sale_entry.html app/templates/dividend_entry.html app/routes.py
git commit -m "feat: add confidence badges and bulk review tables to all entry templates"
```

---

## Task 9: Upload route tests

**Files:**
- Create: `tests/test_upload_routes.py`

**Interfaces:**
- Consumes: all upload routes from Task 7, all parsers from Tasks 2–5, detect from Task 6

- [ ] **Step 1: Write failing upload route tests**

`tests/test_upload_routes.py`:
```python
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
```

- [ ] **Step 2: Run — expect FAIL**

```bash
venv/Scripts/pytest.exe tests/test_upload_routes.py -v
```
Expected: failures (routes/templates not fully wired yet — verify which specific assertions fail)

- [ ] **Step 3: Fix any failures**

For each failing test, identify whether the issue is in the route (routes.py), the template, or the test itself. The most common issues at this stage:
- `flash()` messages not visible: verify the base.html flash block from Task 8 Step 1 is present
- `| enumerate` Jinja filter not registered: verify `app.jinja_env.filters["enumerate"] = enumerate` is in routes.py
- Session not carrying between requests in test client: verify `app.config["TESTING"] = True` is set (already in fixture)

- [ ] **Step 4: Run upload route tests — all must pass**

```bash
venv/Scripts/pytest.exe tests/test_upload_routes.py -v
```
Expected: `11 passed`

- [ ] **Step 5: Run full test suite — all tests must pass**

```bash
venv/Scripts/pytest.exe tests/ -q
```
Expected: `68 passed` (57 original + 7 parser tests from Tasks 1–6 + 11 upload route tests — exact count depends on Task runs above; important: zero failures)

- [ ] **Step 6: Commit**

```bash
git add tests/test_upload_routes.py
git commit -m "feat: add upload route integration tests — v2 complete"
```

---

## Plan self-review

**Spec coverage:**
- 8 document types → 8 parser modules ✓
- Local only, no network → pdfplumber is not in the forbidden-module list, all parsers use `_extract_text()` with no networking ✓
- Both upload + manual paths → upload pre-fills session, manual entry unchanged ✓
- Confidence indicators → green/yellow/orange/red badge CSS + `badge-{confidence}` class on every field ✓
- Bulk review with checkboxes → Task 8 templates, save_bulk branch in routes ✓
- AIS as TDS cross-check → Task 2 (parser), Task 7 (route), Task 8 (form16_entry.html) ✓
- No lot allocations on bulk sale import → sales `save_bulk` branch calls `save_sale_event` only, no `save_sale_lot_allocations` ✓
- Uploaded PDFs never persisted → `_save_upload_to_temp` + `os.unlink(tmp_path)` in finally block ✓

**Placeholder scan:** All steps contain complete code. No TODOs. ✓

**Type consistency:**
- `shares_vested_gross` used in parsers (fidelity_release, schwab_release), route (vesting_upload), template (vesting_entry.html), and test fixtures — matches v1 DB field name ✓
- `shares_withheld_for_tax` same — matches v1 ✓
- `gross_dividend_usd`, `us_tax_withheld_usd` — matches v1 ✓
- Statement parser returns `dict` (not `ParseResult`) — routes access `result["vesting_events"]` and `result["sale_events"]` ✓

**Jinja2 `enumerate` filter:** registered in routes.py Task 8 Step 3 note — critical for bulk review tables. ✓
