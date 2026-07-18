from datetime import date

from flask import Flask, redirect, render_template, request, url_for

from core.models import Form16Summary
from db.access import Database

app = Flask(__name__)
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
    return render_template("year_select.html", ay_label=ay_label) if False else f"Assessment Year: {ay_label}"


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
