from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action

bp = Blueprint("frontdesk", __name__)


@bp.route("/dashboard")
@role_required("frontdesk")
def dashboard():
    today_entries = query_db(
        "SELECT el.*, u.name AS student_name FROM entry_logs el JOIN students s ON el.student_id = s.id "
        "JOIN users u ON s.user_id = u.id WHERE date(el.timestamp) = date('now') ORDER BY el.timestamp DESC LIMIT 15"
    )
    count_today = query_db("SELECT COUNT(*) c FROM entry_logs WHERE date(timestamp) = date('now')", one=True)["c"]
    return render_template("frontdesk/dashboard.html", today_entries=today_entries, count_today=count_today)


@bp.route("/search", methods=["GET", "POST"])
@role_required("frontdesk")
def search():
    student = None
    if request.method == "POST":
        verify_csrf()
        college_id = request.form.get("college_id", "").strip()
        student = query_db(
            "SELECT s.*, u.name, u.phone, u.email FROM students s JOIN users u ON s.user_id = u.id "
            "WHERE s.college_id = ?", (college_id,), one=True,
        )
        if not student:
            flash("No student found with that College ID.", "error")
    return render_template("frontdesk/search.html", student=student)


@bp.route("/entry", methods=["GET", "POST"])
@role_required("frontdesk")
def entry():
    result_student = None
    if request.method == "POST":
        verify_csrf()
        college_id = request.form.get("college_id", "").strip()
        entry_type = request.form.get("entry_type")
        gate = request.form.get("gate", "Main Gate")
        student = query_db(
            "SELECT s.*, u.name FROM students s JOIN users u ON s.user_id = u.id WHERE s.college_id = ?",
            (college_id,), one=True,
        )
        if not student:
            flash("No student found with that College ID.", "error")
        else:
            execute_db(
                "INSERT INTO entry_logs (student_id, college_id, gate, entry_type, operator_id) VALUES (?, ?, ?, ?, ?)",
                (student["id"], college_id, gate, entry_type, session["user_id"]),
            )
            log_action(session["user_id"], f"Entry recorded ({entry_type})", "entry_logs", student["id"])
            flash(f"{entry_type} recorded for {student['name']} at {gate}.", "success")
            result_student = student
    return render_template("frontdesk/entry.html", result_student=result_student)


@bp.route("/assist-request", methods=["GET", "POST"])
@role_required("frontdesk")
def assist_request():
    student = None
    if request.method == "POST":
        verify_csrf()
        if request.form.get("action") == "lookup":
            college_id = request.form.get("college_id", "").strip()
            student = query_db(
                "SELECT s.*, u.name FROM students s JOIN users u ON s.user_id = u.id WHERE s.college_id = ?",
                (college_id,), one=True,
            )
            if not student:
                flash("No student found with that College ID.", "error")
        elif request.form.get("action") == "create":
            student_id = request.form.get("student_id")
            title = request.form.get("title")
            category = request.form.get("category")
            priority = request.form.get("priority", "Normal")
            description = request.form.get("description", "")
            execute_db(
                "INSERT INTO requests (student_id, title, description, category, priority, created_by_role) "
                "VALUES (?, ?, ?, ?, ?, 'frontdesk')",
                (student_id, title, description, category, priority),
            )
            log_action(session["user_id"], "Assisted request created", "requests", student_id, None, title)
            flash("Request created on behalf of student.", "success")
    return render_template("frontdesk/assist_request.html", student=student)
