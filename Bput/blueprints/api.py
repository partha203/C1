import secrets

from flask import Blueprint, current_app, jsonify, request, session
from utils.ai_assistant import AssistantServiceError, ask_campus_assistant
from utils.auth_utils import login_required
from utils.db import query_db

bp = Blueprint("api", __name__)


@bp.route("/health")
def health():
    try:
        query_db("SELECT 1", one=True)
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({"status": "ok" if db_ok else "degraded", "app": "CampusOne", "database": "ok" if db_ok else "error"})


@bp.route("/notifications/unread-count")
@login_required
def unread_count():
    row = query_db("SELECT COUNT(*) c FROM notifications WHERE user_id = ? AND is_read = 0",
                    (session["user_id"],), one=True)
    return jsonify({"unread": row["c"]})


@bp.post("/ai/chat")
def ai_chat():
    if not session.get("user_id"):
        return jsonify({"error": "Please log in to use the assistant."}), 401

    expected_token = session.get("csrf_token")
    supplied_token = request.headers.get("X-CSRFToken", "")
    if not expected_token or not secrets.compare_digest(expected_token, supplied_token):
        return jsonify({"error": "Invalid or missing CSRF token. Refresh the page and try again."}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A valid JSON request body is required."}), 400

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Enter a message before sending."}), 400
    message = message.strip()
    if len(message) > 2000:
        return jsonify({"error": "Messages must be 2,000 characters or fewer."}), 413

    role = session.get("user_role") or session.get("role") or "guest"
    user_name = session.get("user_name") or session.get("name") or "there"
    context = {"user_name": user_name}
    if role == "student":
        student = query_db(
            "SELECT id FROM students WHERE user_id = ?", (session["user_id"],), one=True
        )
        context["student_id"] = student["id"] if student else None

    try:
        bot_response = ask_campus_assistant(message, role, context)
        return jsonify({"response": bot_response})
    except AssistantServiceError:
        return jsonify({"error": "The AI assistant is temporarily unavailable."}), 502
    except Exception:
        current_app.logger.exception("Campus assistant request failed")
        return jsonify({"error": "The assistant could not process your message right now."}), 500
