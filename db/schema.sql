CREATE TABLE IF NOT EXISTS assessment_years (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ay_label TEXT NOT NULL UNIQUE,
    fy_start_date TEXT NOT NULL,
    fy_end_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS form16_summary (
    assessment_year_id INTEGER PRIMARY KEY,
    gross_salary_inr REAL NOT NULL,
    rsu_perquisite_value_inr REAL NOT NULL,
    tds_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS form26as_summary (
    assessment_year_id INTEGER PRIMARY KEY,
    total_tds_tcs_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS vesting_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    vest_date TEXT NOT NULL,
    shares_vested_gross REAL NOT NULL,
    fmv_per_share_usd REAL NOT NULL,
    shares_withheld_for_tax REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS sale_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    sale_date TEXT NOT NULL,
    quantity_sold REAL NOT NULL,
    sale_price_per_share_usd REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS sale_lot_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_event_id INTEGER NOT NULL,
    vesting_event_id INTEGER NOT NULL,
    quantity_allocated REAL NOT NULL,
    FOREIGN KEY (sale_event_id) REFERENCES sale_events(id),
    FOREIGN KEY (vesting_event_id) REFERENCES vesting_events(id)
);

CREATE TABLE IF NOT EXISTS dividend_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    payment_date TEXT NOT NULL,
    gross_dividend_usd REAL NOT NULL,
    us_tax_withheld_usd REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date TEXT PRIMARY KEY,
    rate_inr_per_usd REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_fa_year_selection (
    assessment_year_id INTEGER PRIMARY KEY,
    calendar_year INTEGER NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);

CREATE TABLE IF NOT EXISTS schedule_fa_monthly_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_year_id INTEGER NOT NULL,
    value_date TEXT NOT NULL,
    account_value_inr REAL NOT NULL,
    FOREIGN KEY (assessment_year_id) REFERENCES assessment_years(id)
);
