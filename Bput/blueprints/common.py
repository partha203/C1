from flask import Blueprint, redirect, url_for, session, jsonify, request, render_template, flash, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth_utils import login_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.uploads import save_upload

bp = Blueprint("common", __name__)


@bp.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for(f"{session.get('role')}.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = query_db("SELECT * FROM users WHERE id = ?", (session["user_id"],), one=True)

    if request.method == "POST":
        verify_csrf()
        form_type = request.form.get("form_type")

        if form_type == "profile":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            photo_path = save_upload(request.files.get("photo"), "profile",
                                      current_app.config["ALLOWED_IMAGE_EXT"], current_app.config["UPLOAD_FOLDER"])
            if photo_path:
                execute_db("UPDATE users SET name = ?, phone = ?, photo = ? WHERE id = ?",
                            (name, phone, photo_path, session["user_id"]))
            else:
                execute_db("UPDATE users SET name = ?, phone = ? WHERE id = ?",
                            (name, phone, session["user_id"]))
            session["name"] = name
            log_action(session["user_id"], "Profile updated", "users", session["user_id"])
            flash("Profile updated.", "success")

        elif form_type == "password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")
            if not check_password_hash(user["password_hash"], current_pw):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 4:
                flash("New password must be at least 4 characters.", "error")
            elif new_pw != confirm_pw:
                flash("New password and confirmation do not match.", "error")
            else:
                execute_db("UPDATE users SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(new_pw), session["user_id"]))
                log_action(session["user_id"], "Password changed", "users", session["user_id"])
                flash("Password changed successfully.", "success")

        return redirect(url_for("common.account"))

    return render_template("account.html", user=user)


@bp.route("/toggle-lite-mode", methods=["POST"])
def toggle_lite_mode():
    session["lite_mode"] = not session.get("lite_mode", False)
    nxt = request.form.get("next") or url_for("common.index")
    return redirect(nxt)


@bp.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "CampusOne",
        "short_name": "CampusOne",
        "description": "Campus Life, Debugged.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#4f46e5",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })
