# ITR-2 RSU Assistant v2 — PDF Upload & Auto-Population Design

**Date:** 2026-07-19
**Status:** Approved
**Builds on:** v1 (manual-entry Flask + SQLite app, Tasks 1–17 complete)

---

## Goal

Extend v1 so that Form 16, AIS, Fidelity, and Charles Schwab PDFs can be uploaded directly. The app parses each PDF locally and pre-fills the existing v1 entry forms with confidence indicators. Manual entry remains fully functional as a fallback.

---

## Scope

**In scope:**
- Local PDF parsing (no network, no external API)
- Pre-fill of all existing v1 entry form fields from uploaded PDFs
- Confidence indicators (high / medium / low / missing) per field
- Bulk extraction of multiple events from transaction history PDFs, with a review-before-save table
- AIS as a TDS cross-check source on the Form 16 page

**Out of scope:**
- Automatic FX rate extraction from any PDF (FX rates remain manual CSV upload)
- Multi-year batch processing
- Parsing PDFs other than the eight document types listed below
- Any network call, cloud storage, or external LLM for parsing

---

## Architecture

v2 adds three things to the v1 codebase. No existing code is modified except the entry form templates and `app/routes.py`.

```
core/
  parsers/
    __init__.py
    _base.py            # ParsedField dataclass, ParseResult type alias, shared helpers
    form16.py           # Form16Parser
    ais.py              # AISParser
    fidelity_release.py # FidelityReleaseParser
    fidelity_tax.py     # FidelityTaxParser
    fidelity_statement.py # FidelityStatementParser (transaction history)
    schwab_release.py   # SchwabReleaseParser
    schwab_tax.py       # SchwabTaxParser
    schwab_statement.py # SchwabStatementParser (transaction history)

app/
  routes.py             # new upload endpoints added; existing routes untouched
  templates/
    form16_entry.html   # upload button + confidence badges added
    vesting_entry.html  # upload button + bulk review table added
    sale_entry.html     # upload button + bulk review table added
    dividend_entry.html # upload button + confidence badges added

tests/
  parser_fixtures/
    form16_sample.txt
    ais_sample.txt
    fidelity_release_sample.txt
    fidelity_tax_sample.txt
    fidelity_statement_sample.txt
    schwab_release_sample.txt
    schwab_tax_sample.txt
    schwab_statement_sample.txt
  test_parser_form16.py
  test_parser_ais.py
  test_parser_fidelity.py
  test_parser_schwab.py
  test_upload_routes.py
```

`pdfplumber` is the only new dependency. It is open source (MIT). No other new packages.

---

## Parser Interface

Every parser module exposes a single public function:

```python
def parse(pdf_path: str) -> ParseResult: ...
```

`ParseResult` is defined in `core/parsers/_base.py`:

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class ParsedField:
    value: Any          # None if not found
    confidence: str     # "high" | "medium" | "low" | "missing"
    source_hint: str    # e.g. "page 2, label 'TDS Deducted'"

ParseResult = dict[str, ParsedField]
```

**Confidence rules (applied consistently across all parsers):**

| Level | Meaning |
|---|---|
| `high` | Exact label found; value parsed without ambiguity |
| `medium` | Label found but value needed cleanup (comma-stripped number, date reformatted) |
| `low` | Value inferred from context, not a direct label match |
| `missing` | Field not found; corresponding form field left empty |

Parsers never raise exceptions for missing fields — they return `missing` confidence. Exceptions are only raised for unreadable PDFs (pdfplumber failure) or corrupt input.

---

## Document-to-Field Mapping

| Document | Parser | v1 Fields Populated |
|---|---|---|
| Form 16 | `Form16Parser` | `gross_salary_inr`, `rsu_perquisite_value_inr`, `tds_inr` |
| AIS | `AISParser` | `tds_inr` (cross-check only — shown alongside Form 16 value) |
| Fidelity RSU Release Confirmation | `FidelityReleaseParser` | `vest_date`, `shares_released`, `fmv_per_share_usd`, `tax_withheld_shares` |
| Fidelity 1042-S / 1099-DIV | `FidelityTaxParser` | `dividend_usd`, `withholding_tax_usd` |
| Fidelity Transaction History | `FidelityStatementParser` | multiple `VestingEvent` + `SaleEvent` records |
| Schwab RSU Release Confirmation | `SchwabReleaseParser` | `vest_date`, `shares_released`, `fmv_per_share_usd`, `tax_withheld_shares` |
| Schwab 1042-S / 1099-DIV | `SchwabTaxParser` | `dividend_usd`, `withholding_tax_usd` |
| Schwab Transaction History | `SchwabStatementParser` | multiple `VestingEvent` + `SaleEvent` records |

The AIS parser populates `tds_inr` only. It does not replace Form 16 data — it is displayed as a second value on the Form 16 entry page so discrepancies are immediately visible.

---

## Upload UX

No new pages. Every upload lives on an existing v1 entry page.

### Single-event pages (Form 16, Dividends)

An "Upload PDF" button appears above the entry form. On upload:
1. File is sent via `multipart/form-data POST` to the upload endpoint.
2. Parser runs server-side; result is stored in Flask session.
3. Page redirects back to the entry form (GET).
4. Fields pre-filled from session values show a colored confidence dot:
   - Green dot = `high`
   - Yellow dot = `medium`
   - Orange dot = `low`
   - Red dot / empty = `missing`
5. User reviews, corrects any red/orange fields, and submits normally.
6. Session data is cleared after the form is saved.

### Bulk-event pages (Vesting, Sales — transaction history only)

After parsing a transaction history PDF:
1. A review table is shown listing all extracted events with a confidence badge per row.
2. Each row has a checkbox (checked by default).
3. User unchecks rows to skip, then clicks "Save selected."
4. Only checked rows are written to the DB.
5. The review table is not stored in the DB — it lives in the session only until submitted.

### AIS cross-check (Form 16 page only)

When an AIS PDF is uploaded on the Form 16 page, the extracted TDS value is shown as a second read-only field beneath the Form 16 TDS field with the label "AIS TDS (cross-check)." If the two values differ, both fields are highlighted in yellow. No automatic reconciliation — the user decides which value to use.

---

## Upload Endpoints

New routes added to `app/routes.py`:

```
POST /year/<ay_label>/form16/upload          → Form16Parser or AISParser (detected by content)
POST /year/<ay_label>/vesting/upload         → FidelityReleaseParser | SchwabReleaseParser
POST /year/<ay_label>/vesting/upload-bulk    → FidelityStatementParser | SchwabStatementParser
POST /year/<ay_label>/sales/upload-bulk      → FidelityStatementParser | SchwabStatementParser
POST /year/<ay_label>/dividends/upload       → FidelityTaxParser | SchwabTaxParser
```

**Document type detection:** the parser is selected by scanning the first page of extracted text for known document signatures (e.g., "Fidelity Investments" + "Release Confirmation", "Charles Schwab", "Annual Information Statement"). Detection logic lives in `core/parsers/__init__.py` as `detect_document_type(pdf_path) -> str`.

**File handling:** uploaded PDFs are written to a temp file, parsed, then deleted. They are never persisted to disk beyond the duration of the request.

---

## Testing

Real PDFs cannot be committed (personal financial data). Tests use **text snapshot fixtures** — plain `.txt` files containing the raw text that pdfplumber would extract from a real PDF, with all real numbers replaced by dummy values (same structure, same labels, fake amounts).

Each parser test verifies:
1. All expected fields extract at `high` or `medium` confidence from the fixture.
2. A deliberately truncated fixture returns `missing` for the removed field, not an exception.
3. The no-network guardrail (existing `test_no_network.py`) continues to pass — `pdfplumber` is not in the forbidden module list but no networking imports are introduced.

Upload route tests (`test_upload_routes.py`) use a small synthetic PDF generated in-test with `pdfplumber`-compatible text, verifying that a multipart POST pre-fills the session and the subsequent GET renders confidence badges.

**Fixture creation process:** the user runs the real app against their actual PDFs on first use. If any field shows `missing`, they note the exact label text from their PDF and report it; the corresponding parser regex is updated. This is expected on first run — fixture files are seeded from the first successful real parse, then anonymized and committed.

---

## Constraints (inherited from v1, all still enforced)

- No network calls in `core/` or `app/` — enforced by `test_no_network.py`.
- No default/fallback values for tax-affecting fields — `missing` confidence means the field stays empty, not zero-filled.
- All uploaded PDFs are temp-only; never persisted.
- No credentials or PII in code, fixtures, or git history.

---

## Dependencies

| Package | Version | License | Purpose |
|---|---|---|---|
| `pdfplumber` | `>=0.11` | MIT | PDF text and table extraction |

Added to `requirements.txt`. All other dependencies unchanged from v1.

---

## Open Risk

PDF layouts for Fidelity and Schwab change without notice. Parsers will need updating when broker PDF formats change. This is accepted — the confidence-indicator system makes silent failures visible, and the manual fallback means a layout change never blocks the user from completing their filing.
