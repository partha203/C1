from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.notify import notify_user

bp = Blueprint("mess", __name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEALS = ["Breakfast", "Lunch", "Snacks", "Dinner"]


@bp.route("/dashboard")
@role_required("mess")
def dashboard():
    feedback_count = query_db("SELECT COUNT(*) c FROM mess_feedback", one=True)["c"]
    avg_rating = query_db("SELECT ROUND(AVG(rating),2) a FROM mess_feedback", one=True)["a"] or 0
    complaints = query_db(
        "SELECT COUNT(*) c FROM requests WHERE category = 'Mess' AND status NOT IN ('Resolved','Rejected')",
        one=True,
    )["c"]
    recent_feedback = query_db(
        "SELECT mf.*, u.name AS student_name FROM mess_feedback mf JOIN students s ON mf.student_id = s.id "
        "JOIN users u ON s.user_id = u.id ORDER BY mf.created_at DESC LIMIT 10"
    )
    by_meal = query_db(
        "SELECT meal, ROUND(AVG(rating),2) avg_rating, COUNT(*) c FROM mess_feedback GROUP BY meal"
    )
    return render_template("mess/dashboard.html", feedback_count=feedback_count, avg_rating=avg_rating,
                            complaints=complaints, recent_feedback=recent_feedback, by_meal=by_meal)


@bp.route("/menu", methods=["GET", "POST"])
@role_required("mess")
def menu():
    if request.method == "POST":
        verify_csrf()
        day = request.form.get("day_of_week")
        meal = request.form.get("meal")
        items = request.form.get("items", "")
        execute_db(
            "INSERT INTO mess_menus (day_of_week, meal, items, updated_at) VALUES (?, ?, ?, datetime('now')) "
            "ON CONFLICT(day_of_week, meal) DO UPDATE SET items = excluded.items, updated_at = datetime('now')",
            (day, meal, items),
        )
        log_action(session["user_id"], "Mess menu updated", "mess_menus", None, None, f"{day} {meal}")
        flash("Menu updated.", "success")
        return redirect(url_for("mess.menu"))

    rows = query_db("SELECT * FROM mess_menus")
    grid = {d: {m: "" for m in MEALS} for d in DAYS}
    for r in rows:
        if r["day_of_week"] in grid:
            grid[r["day_of_week"]][r["meal"]] = r["items"]
    return render_template("mess/menu.html", grid=grid, days=DAYS, meals=MEALS)


@bp.route("/feedback")
@role_required("mess")
def feedback():
    rows = query_db(
        "SELECT mf.*, u.name AS student_name FROM mess_feedback mf JOIN students s ON mf.student_id = s.id "
        "JOIN users u ON s.user_id = u.id ORDER BY mf.created_at DESC LIMIT 200"
    )
    return render_template("mess/feedback.html", feedback=rows)


@bp.route("/complaints")
@role_required("mess")
def complaints():
    rows = query_db(
        "SELECT r.*, u.name AS student_name FROM requests r JOIN students s ON r.student_id = s.id "
        "JOIN users u ON s.user_id = u.id WHERE r.category = 'Mess' ORDER BY r.created_at DESC"
    )
    return render_template("mess/complaints.html", requests=rows)


@bp.route("/complaints/<int:rid>", methods=["POST"])
@role_required("mess")
def update_complaint(rid):
    verify_csrf()
    new_status = request.form.get("status")
    note = request.form.get("note", "")
    req = query_db("SELECT * FROM requests WHERE id = ?", (rid,), one=True)
    execute_db(
        "UPDATE requests SET status = ?, resolution_note = ?, updated_at = datetime('now'), "
        "assigned_to = 'Mess Manager', assigned_at = COALESCE(assigned_at, datetime('now')) WHERE id = ?",
        (new_status, note, rid),
    )
    execute_db(
        "INSERT INTO request_updates (request_id, updated_by, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
        (rid, session["user_id"], req["status"], new_status, note),
    )
    if new_status != req["status"] and req["student_id"]:
        student = query_db("SELECT user_id FROM students WHERE id = ?", (req["student_id"],), one=True)
        if student:
            notify_user(student["user_id"], "request", f"Request update: {req['title']}",
                        f"Status changed to {new_status}.", url_for("student.request_detail", rid=rid))
    flash("Complaint updated.", "success")
    return redirect(url_for("mess.complaints"))
