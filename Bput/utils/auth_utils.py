import functools
import secrets
from flask import session, redirect, url_for, request, abort, flash


def login_required(view):
    @functools.wraps(view)
    def wrapped(**kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(**kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapped(**kwargs):
            if session.get("user_id") is None:
                return redirect(url_for("auth.login", next=request.path))
            if session.get("role") not in roles:
                abort(403)
            return view(**kwargs)
        return wrapped
    return decorator


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")


def gen_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def verify_csrf():
    token = session.get("csrf_token")
    sent = request.form.get("csrf_token")
    if not token or not sent or token != sent:
        abort(400, description="Invalid or missing CSRF token. Please refresh and try again.")
