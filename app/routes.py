from datetime import date

from flask import Flask, redirect, render_template, request, url_for

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
