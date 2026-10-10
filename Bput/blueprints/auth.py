import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth_utils import verify_csrf
from utils.db import get_db, query_db
from utils.audit import log_action

bp = Blueprint("auth", __name__)

ROLE_DASHBOARD = {
    "student": "student.dashboard",
    "faculty": "faculty.dashboard",
    "admin": "admin.dashboard",
    "warden": "warden.dashboard",
    "mess": "mess.dashboard",
    "frontdesk": "frontdesk.dashboard",
}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query_db("SELECT * FROM users WHERE email = ? AND is_active = 1", (email,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.permanent = True
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            log_action(user["id"], "Login", "users", user["id"])
            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            return redirect(url_for(ROLE_DASHBOARD.get(user["role"], "common.index")))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("user_id"):
        return redirect(url_for("common.index"))

    if request.method == "POST":
        verify_csrf()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        college_id = request.form.get("college_id", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not college_id or "@" not in email:
            flash("Enter your name, a valid email, and your college ID.", "error")
        elif len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif query_db("SELECT id FROM users WHERE email = ?", (email,), one=True):
            flash("An account with that email already exists.", "error")
        elif query_db("SELECT id FROM students WHERE college_id = ?", (college_id,), one=True):
            flash("An account with that college ID already exists.", "error")
        else:
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (email, password_hash, role, name, phone) VALUES (?, ?, 'student', ?, ?)",
                    (email, generate_password_hash(password), name, phone or None),
                )
                user_id = cursor.lastrowid
                db.execute(
                    "INSERT INTO students (user_id, college_id) VALUES (?, ?)",
                    (user_id, college_id),
                )
                db.commit()
            except sqlite3.IntegrityError:
                db.rollback()
                flash("An account with that email or college ID already exists.", "error")
                return render_template("signup.html")

            session.clear()
            session.permanent = True
            session["user_id"] = user_id
            session["role"] = "student"
            session["name"] = name
            log_action(user_id, "Account created", "users", user_id)
            return redirect(url_for("student.dashboard"))

    return render_template("signup.html")


@bp.route("/logout")
def logout():
    uid = session.get("user_id")
    if uid:
        log_action(uid, "Logout", "users", uid)
    session.clear()
    return redirect(url_for("auth.login"))
