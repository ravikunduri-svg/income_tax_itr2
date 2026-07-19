import csv
import io
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

from core.fx import FXRateTable, MissingFXRateError
from core.models import Form16Summary
from core.report import build_report
from db.access import Database

app = Flask(__name__)
app.secret_key = "itr2-rsu-dev-secret"
_db_path_holder = {"path": None}


def configure_db(db_path: str) -> None:
    _db_path_holder["path"] = db_path


def get_db() -> Database:
    if _db_path_holder["path"] is None:
        raise RuntimeError("Database path not configured. Call configure_db() first.")
    return Database(_db_path_holder["path"])


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        ay_label = request.form["ay_label"]
        fy_start = date.fromisoformat(request.form["fy_start_date"])
        fy_end = date.fromisoformat(request.form["fy_end_date"])
        get_db().create_or_get_assessment_year(ay_label, fy_start, fy_end)
        return redirect(url_for("year_detail", ay_label=ay_label))
    return render_template("year_select.html")


@app.route("/year/<ay_label>")
def year_detail(ay_label: str):
    return render_template("dashboard.html", ay_label=ay_label)


@app.route("/year/<ay_label>/form16", methods=["GET", "POST"])
def form16_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_form16_summary(
            ay_id,
            gross_salary_inr=float(request.form["gross_salary_inr"]),
            rsu_perquisite_value_inr=float(request.form["rsu_perquisite_value_inr"]),
            tds_inr=float(request.form["tds_inr"]),
        )
        return redirect(url_for("year_detail", ay_label=ay_label))
    form16 = db.get_form16_summary(ay_id)
    return render_template("form16_entry.html", ay_label=ay_label, form16=form16)


@app.route("/year/<ay_label>/vesting", methods=["GET", "POST"])
def vesting_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_vesting_event(
            ay_id,
            vest_date=date.fromisoformat(request.form["vest_date"]),
            shares_vested_gross=float(request.form["shares_vested_gross"]),
            fmv_per_share_usd=float(request.form["fmv_per_share_usd"]),
            shares_withheld_for_tax=float(request.form["shares_withheld_for_tax"]),
        )
        return redirect(url_for("vesting_entry", ay_label=ay_label))
    vesting_events = db.list_vesting_events(ay_id)
    return render_template("vesting_entry.html", ay_label=ay_label, vesting_events=vesting_events)


@app.route("/year/<ay_label>/sales", methods=["GET", "POST"])
def sale_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    vesting_events = db.list_vesting_events(ay_id)

    if request.method == "POST":
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
    return render_template("sale_entry.html", ay_label=ay_label, vesting_events=vesting_events, sale_events=sale_events)


@app.route("/year/<ay_label>/dividends", methods=["GET", "POST"])
def dividend_entry(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_dividend_event(
            ay_id,
            payment_date=date.fromisoformat(request.form["payment_date"]),
            gross_dividend_usd=float(request.form["gross_dividend_usd"]),
            us_tax_withheld_usd=float(request.form["us_tax_withheld_usd"]),
        )
        return redirect(url_for("dividend_entry", ay_label=ay_label))
    dividend_events = db.list_dividend_events(ay_id)
    return render_template("dividend_entry.html", ay_label=ay_label, dividend_events=dividend_events)


@app.route("/year/<ay_label>/fx-rates", methods=["GET", "POST"])
def fx_upload(ay_label: str):
    db = get_db()
    if request.method == "POST":
        file = request.files["fx_csv"]
        content = file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rates = {date.fromisoformat(row["date"]): float(row["rate"]) for row in reader}
        db.upsert_fx_rates(rates)
        return redirect(url_for("fx_upload", ay_label=ay_label))
    rates = dict(sorted(db.get_all_fx_rates().items()))
    return render_template("fx_upload.html", ay_label=ay_label, rates=rates)


@app.route("/year/<ay_label>/schedule-fa", methods=["GET", "POST"])
def schedule_fa_confirm(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())
    if request.method == "POST":
        db.save_schedule_fa_calendar_year(ay_id, int(request.form["calendar_year"]))
        db.save_schedule_fa_monthly_value(
            ay_id,
            value_date=date.fromisoformat(request.form["value_date"]),
            account_value_inr=float(request.form["account_value_inr"]),
        )
        return redirect(url_for("schedule_fa_confirm", ay_label=ay_label))
    calendar_year = db.get_schedule_fa_calendar_year(ay_id)
    monthly_values = dict(sorted(db.get_schedule_fa_monthly_values(ay_id).items()))
    return render_template("schedule_fa_confirm.html", ay_label=ay_label, calendar_year=calendar_year, monthly_values=monthly_values)


@app.route("/year/<ay_label>/results")
def results(ay_label: str):
    db = get_db()
    ay_id = db.create_or_get_assessment_year(ay_label, date.today(), date.today())

    form16 = db.get_form16_summary(ay_id)
    vesting_events = db.list_vesting_events(ay_id)
    sales_with_allocations = db.list_sale_events_with_allocations(ay_id)
    sale_events = [s for s, _ in sales_with_allocations]
    allocations_by_sale = {s.id: allocs for s, allocs in sales_with_allocations}
    dividend_events = db.list_dividend_events(ay_id)
    fx_rates = db.get_all_fx_rates()
    schedule_fa_calendar_year = db.get_schedule_fa_calendar_year(ay_id)
    schedule_fa_monthly_values = db.get_schedule_fa_monthly_values(ay_id)

    if form16 is None:
        return render_template("results.html", ay_label=ay_label, error="Form 16 data hasn't been entered yet.")

    fx_table = FXRateTable(fx_rates)

    try:
        report = build_report(
            form16=form16,
            vesting_events=vesting_events,
            sale_events=sale_events,
            allocations_by_sale=allocations_by_sale,
            dividend_events=dividend_events,
            fx_table=fx_table,
            schedule_fa_calendar_year=schedule_fa_calendar_year,
            schedule_fa_monthly_values=schedule_fa_monthly_values,
        )
    except MissingFXRateError as e:
        return render_template("results.html", ay_label=ay_label, error=str(e))
    except ValueError as e:
        return render_template("results.html", ay_label=ay_label, error=str(e))

    return render_template("results.html", ay_label=ay_label, report=report, error=None)
