# ITR-2 RSU Assistant — Design Spec

**Date:** 2026-07-16
**Status:** Approved by user, pending spec self-review sign-off
**Owner:** Ravi Kiran Kunduri

## Purpose

A local-only calculation aid for preparing ITR-2 (India) as a tax resident with US-employer RSU income (Broadcom, via Schwab/Fidelity). It takes manually-entered figures from Form 16, Form 26AS, and brokerage vesting/sale/dividend records, and produces a per-schedule breakdown of computed values to manually transcribe into the government e-filing portal.

**This is a calculation aid, not tax advice and not a filer.** It never connects to the internet, never submits anything to the Income Tax portal, and never guesses a value it isn't given.

## Governing principle: confidence-gated logic

Every calculation rule in this app falls into one of two categories, and the design must keep them visibly distinct:

1. **Confident, hardcoded rules** — well-established, stable tax rules implemented directly in code (example: the 24-month LTCG threshold for unlisted foreign shares, computed via exact calendar-month arithmetic from acquisition date to transfer date).
2. **Uncertain or year-to-year-variable rules** — anything with genuine ambiguity, jurisdiction-specific nuance, or annual regulatory change risk (example: which exact SBI rate variant to use, or which calendar year maps to which assessment year for Schedule FA). **These are never hardcoded as an assumption.** The app requires the user to explicitly specify or confirm the value, and recommends CA confirmation in the UI copy at that point.

This principle is the direct implementation of "cannot hallucinate or assume."

## Architecture

```
itr2-rsu-assistant/
├── core/                   # Pure Python, zero Flask/network dependencies
│   ├── models.py           # Dataclasses: VestingEvent, SaleEvent, DividendEvent,
│   │                       # Form16Summary, Form26ASSummary, FXRateTable
│   ├── fx.py                # Rate lookup — hard-stop (raises) on missing date
│   ├── capital_gains.py      # Per-sale gain computation + LTCG/STCG classification
│   ├── schedule_fa.py        # Foreign-asset peak/closing value, user-confirmed calendar-year window
│   ├── cross_check.py        # Form 16 vs. vesting-sum perquisite mismatch detection
│   ├── ftc.py                 # Foreign tax credit computation + Form 67 deadline warning
│   └── report.py              # Assembles the final per-schedule output
├── app/                     # Flask web layer — routes and templates only, no calculation logic
│   ├── routes.py
│   └── templates/
├── db/
│   └── schema.sql            # SQLite schema, one saved record per assessment year
├── tests/
│   ├── golden_cases/          # Hand-computed worked examples — the eval suite
│   └── test_no_network.py     # Structural guardrail: fails if any networking import
│                               # appears anywhere under core/ or app/
├── requirements.txt          # Flask, pytest — nothing else
└── run.py                    # Entry point: starts local Flask dev server
```

**Why `core/` is separate from `app/`:** the calculation engine must be independently testable without a running web server, and must be structurally incapable of making a network call — the no-network test scans `core/` (and `app/`) source for forbidden imports (`requests`, `urllib.request`, `socket`, `http.client`) and fails the build if any appear.

## Data model (SQLite, one row per assessment year)

- `assessment_years` — AY label, FY start/end dates, created/updated timestamps.
- `form16_summary` — gross salary, RSU perquisite value (as reported by employer), TDS, per AY.
- `form26as_summary` — TDS/TCS credit entries, per AY.
- `vesting_events` — vest date, shares vested, FMV/share (USD), shares withheld for tax, per AY.
- `sale_events` — sale date, sale price/share (USD), per AY.
- `sale_lot_allocations` — links a sale event to one or more vesting events with an explicit quantity drawn from each. **No automatic FIFO or any other lot-matching assumption** — the user enters exactly which lot(s) a sale came from and how many shares from each. If total allocated quantity doesn't match the sale's total quantity, the app blocks the calculation and shows the discrepancy rather than guessing the remainder.
- `dividend_events` — payment date, gross dividend (USD), US tax withheld (USD), per AY.
- `fx_rates` — date, rate (INR per USD), user-supplied, uploaded once and reusable across years.
- `schedule_fa_year_selection` — the user's explicit confirmation of which calendar year applies to Schedule FA for this AY (per the confidence-gating principle above — never inferred).

## Data flow

1. Create or reopen an assessment year.
2. Enter Form 16 and Form 26AS summary figures (manual entry, per the earlier decision).
3. Enter vesting events, sale events, dividend events (manual structured forms).
4. Upload/extend the FX-rate CSV (date → rate). Reusable across years; the app tells you exactly which dates from your current transactions are missing before you can proceed.
5. Confirm the calendar year to use for Schedule FA for this AY (explicit UI step, not inferred).
6. Run the calculation. Any missing FX rate blocks that specific transaction's calculation and is listed by date — nothing else in the report is silently skipped or defaulted.
7. Results view: per-schedule breakdown (Salary, Capital Gains, Foreign Assets, TR/FSI, Other Sources), each number shown with its formula, inputs, and the exact rate/date used. Any Form 16-vs-vesting mismatch is shown as a visible warning, not resolved automatically.
8. You manually transcribe values into the government e-filing portal. The app never attempts this itself.

## Calculation specifications

**Capital gains per sale:**
- Computed per lot allocation, then summed for the sale: for each vesting event a sale draws from, cost basis (INR) = FMV/share (USD) at that vest × shares allocated from that lot × user-supplied FX rate for **that vest's date**.
- Sale proceeds (INR) = sale price/share (USD) × total shares sold × user-supplied FX rate for the **sale date**, apportioned across lots in proportion to each lot's allocated quantity.
- Gain (INR) = Sale proceeds − Cost basis, computed per lot (since different lots may have different vest dates and therefore different LTCG/STCG classifications for the same sale).
- Lot matching is always explicit user input (see `sale_lot_allocations` above) — never an inferred FIFO or average-cost assumption.
- The app does not decide which specific SBI rate variant (TT buying/selling) is correct for either leg — that's the user's/CA's responsibility when building the FX-rate CSV. The app's guarantee is deterministic date-matching and full traceability, not tax-law interpretation of rate selection.

**LTCG/STCG classification (confident, hardcoded rule):**
- Holding period = exact calendar-month difference between vest date and sale date.
- More than 24 months → LTCG. 24 months or less → STCG.
- Computed via calendar-month arithmetic (add 24 months to the vest date, respecting month-length/leap-year rules; compare against the sale date) — not a fixed 730-day approximation, which would misclassify sales near the boundary in some years.
- Any sale within 5 calendar days of the 24-month boundary is flagged prominently in the output, regardless of which side it falls on.

**Schedule FA (uncertain rule — explicit user confirmation, not hardcoded):**
- The app asks the user which calendar year (Jan 1–Dec 31) applies to Schedule FA for the current assessment year, with UI copy recommending CA confirmation.
- Peak value = highest of the account values the user enters across that confirmed calendar year (from monthly/year-end statements).
- Closing value = Dec 31 value of that confirmed calendar year.
- This window is computed and displayed completely separately from the FY window used for Schedule CG/Salary — the UI never shows them merged or lets one silently substitute for the other.

**Foreign tax credit:**
- Computed from dividend withholding entries.
- The output includes a non-dismissable reminder that Form 67 must be filed before the ITR-2 deadline, not with it, if FTC is being claimed.

**Cross-check:**
- Sum of vesting-event FMV values (as perquisite) is compared against the Form 16-reported RSU perquisite figure.
- Any non-zero difference is shown as a warning with both numbers displayed — the app never picks one as "correct."

## Guardrails (summary — see calculation specs above for detail)

1. Hard stop on any missing FX rate for a needed transaction date.
2. Every output number shows its formula, inputs, and rate/date used.
3. Form 16 vs. vesting mismatch → visible warning, never auto-resolved.
4. 24-month LTCG boundary computed exactly via calendar-month arithmetic; near-boundary sales flagged.
5. No default/fallback values for any tax-affecting field — blank means "cannot compute this," never zero.
6. Structural no-network test over `core/` and `app/` source.
7. Schedule FA calendar-year window is user-confirmed, never inferred, and never conflated with the FY window.
8. Persistent, non-dismissable disclaimer: calculation aid only, not tax advice, review with a CA before filing.

## Eval suite (`tests/golden_cases/`)

Hand-computed worked examples, each with full shown arithmetic as ground truth, committed alongside the code:

1. **Standard case** — one vest, one sale, comfortably past the 24-month mark → LTCG, verify exact INR gain.
2. **STCG case** — vest and sale less than 24 months apart → verify STCG classification and gain.
3. **Boundary case, exactly 24 months** — sale date is exactly 24 calendar months after vest date → must classify as STCG (not more than 24 months).
4. **Boundary case, 24 months + 1 day** — must classify as LTCG.
5. **Missing FX rate** — a transaction date has no matching CSV entry → must raise a blocking error naming the missing date, not silently skip or substitute.
6. **Form 16/vesting mismatch** — perquisite figures differ → must produce the warning with both values shown.
7. **Dividend + FTC** — dividend with US withholding → verify FTC figure and the Form 67 deadline reminder appears.
8. **Cross-calendar-year transaction** — a transaction whose FY bucket (Schedule CG) and confirmed Schedule-FA calendar-year bucket differ → verify the two schedules never share or leak a value between them.
9. **Split-lot sale** — one sale drawing from two vesting events with different vest dates, where one lot qualifies as LTCG and the other as STCG for the same sale → verify the gain is correctly split and classified per lot, not merged into a single classification.
10. **Mismatched lot allocation** — a sale's lot allocations don't sum to its total quantity sold → must block with a clear discrepancy message, not silently compute using only the allocated portion.

**Standing rule:** no change to any file under `core/` ships unless every golden case still passes. This is enforced by running the full `tests/golden_cases/` suite as part of any change to calculation logic — not optional, not a "should probably run this."

## Field-level input guidance (surfaced inline in the UI, not just here)

Every data-entry field must show, right next to it, what it is and which document it comes from — not just a bare label. This is a UI requirement, not only documentation: each field in `app/templates/` gets a visible hint, not a tooltip that has to be discovered.

| Field | What it is | Where to find it |
|---|---|---|
| Gross Salary | Total salary income for the FY | Form 16 Part B, "Details of Salary Paid" section |
| RSU Perquisite Value (employer-reported) | The RSU vesting value your employer already taxed as salary | Form 16 Part B, under "Value of perquisites u/s 17(2)" — may be a separate line if your employer breaks it out |
| TDS (Tax Deducted at Source) | Tax your employer withheld from salary | Form 16 Part A, "Total tax deducted" summary, or Part B "Total Tax Payable" |
| Form 26AS TDS/TCS entries | Tax-credit records matching Form 16 | Form 26AS, Part A (TDS on Salary) and Part A2/B as applicable — deductor name, section, amount, date per entry |
| Vest date | Date RSUs vested/released | Schwab "Release Confirmation" or Fidelity Stock Plan release statement — "Vest Date" / "Release Date" |
| Shares vested (gross) | Total shares released at vesting, before tax withholding | Same statement — "Shares Released" / "Gross Shares" |
| FMV per share at vest (USD) | Fair market value used to compute your taxable perquisite | Same statement — "Fair Market Value" / "FMV per Share" |
| Shares withheld for tax | Shares your employer sold to cover withholding | Same statement — "Shares Withheld for Taxes" / "Shares Sold to Cover Taxes" |
| Sale date | Date shares were sold | Schwab "Realized Gain/Loss" report or trade confirmation — "Trade Date" / "Date Sold" |
| Quantity sold | Number of shares sold in this transaction | Same report — "Quantity" |
| Sale price per share (USD) | Price received per share | Same report — "Sale Price" / "Price per Share" |
| Dividend payment date | Date dividend was paid | 1042-S or 1099-DIV, or brokerage dividend statement — "Payment Date" |
| Gross dividend (USD) | Dividend amount before withholding | 1042-S Box 2 ("Gross Income") or 1099-DIV Box 1a |
| US tax withheld on dividend (USD) | Tax the US withheld at source | 1042-S Box 7a ("Federal tax withheld") or 1099-DIV Box 4 |
| FX rate (INR per USD) per date | The conversion rate to apply for that transaction date | Sourced by you/your CA — typically SBI's published TT rate for that date. The app does not fetch or verify this; you supply one rate per date in the CSV |
| Schedule FA calendar-year selection | Which Jan–Dec window applies to Schedule FA for this AY | This is a filing-method decision, not something read off a document — confirm with your CA, since it's the kind of rule this app deliberately does not assume (see Governing Principle) |

If a field's guidance can't be written this concretely during implementation (i.e., it's genuinely ambiguous which document/box applies), that's a signal to make it a user-confirmed decision point per the Governing Principle, not to write vague guidance and move on.

## Testing strategy beyond the golden cases

- `test_no_network.py` — static source scan, fails the build if `core/` or `app/` imports any networking-capable module.
- Standard unit tests for each `core/` module in isolation (not just the end-to-end golden cases).
- Manual smoke test of the Flask UI (form entry → results view) before considering v1 done — no automated browser testing in v1 scope.

## Out of scope for v1

- PDF/CSV parsing of Form 16, Form 26AS, or brokerage statements — all manual entry (per earlier decision).
- Any e-filing portal integration, scraping, or submission.
- Multi-year comparison/reporting views (v1 stores one record per AY, reopenable, no cross-year analytics).
- Any network call of any kind, including for exchange rates (user-supplied CSV only).
