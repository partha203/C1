"""
AI Campus Assistant abstraction.

Core CampusOne functionality never depends on this. If no AI backend is
configured (GEMINI_API_KEY or OLLAMA_HOST), a rule-based engine answers
common questions directly from the database, so the assistant always works.
"""
import json
from datetime import datetime
from flask import current_app
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from utils.db import query_db


class AssistantServiceError(Exception):
    pass


def answer_question(student_id, question):
    q = question.lower()

    if "attendance" in q:
        rows = query_db(
            "SELECT s.name AS subject, "
            "SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present, COUNT(*) AS total "
            "FROM attendance a JOIN subjects s ON a.subject_id = s.id "
            "WHERE a.student_id = ? GROUP BY a.subject_id", (student_id,),
        )
        if not rows:
            return "No attendance records found yet."
        total_p = sum(r["present"] for r in rows)
        total_t = sum(r["total"] for r in rows)
        pct = round((total_p / total_t) * 100, 1) if total_t else 0
        return f"Your overall attendance is {pct}% ({total_p}/{total_t} classes). Ask about a specific subject for details."

    if "exam" in q:
        row = query_db(
            "SELECT e.name, sub.name AS subject, e.date, e.time, e.room "
            "FROM exams e JOIN subjects sub ON e.subject_id = sub.id "
            "JOIN students st ON st.section_id = e.section_id "
            "WHERE st.id = ? AND e.date >= ? ORDER BY e.date LIMIT 1",
            (student_id, datetime.now().strftime("%Y-%m-%d")), one=True,
        )
        if not row:
            return "No upcoming exams found on your schedule."
        return f"Your next exam is {row['name']} ({row['subject']}) on {row['date']} at {row['time']}, Room {row['room']}."

    if "mess" in q or "menu" in q:
        today = datetime.now().strftime("%A")
        rows = query_db("SELECT meal, items FROM mess_menus WHERE day_of_week = ? ORDER BY meal", (today,))
        if not rows:
            return "Today's mess menu hasn't been published yet."
        parts = [f"{r['meal']}: {r['items']}" for r in rows]
        return f"Today's menu ({today}) — " + "; ".join(parts)

    if "complaint" in q or "request" in q or "hostel" in q:
        row = query_db(
            "SELECT title, status, category FROM requests WHERE student_id = ? ORDER BY created_at DESC LIMIT 1",
            (student_id,), one=True,
        )
        if not row:
            return "You have no requests or complaints on file."
        return f"Your most recent request '{row['title']}' ({row['category']}) is currently: {row['status']}."

    return ("I can help with attendance, exam schedule, mess menu, and request/complaint status. "
            "Try asking, e.g. 'What is my attendance?' or 'What's today's mess menu?'")


def is_llm_configured():
    cfg = current_app.config
    return bool(cfg.get("GEMINI_API_KEY") or cfg.get("OLLAMA_HOST"))


def ask_campus_assistant(message, role, context=None):
    context = context or {}
    student_id = context.get("student_id")

    # Keep personal campus data on the local database-backed path.
    if role == "student" and student_id and any(
        topic in message.lower()
        for topic in ("attendance", "exam", "mess", "menu", "complaint", "request", "hostel")
    ):
        return answer_question(student_id, message)

    api_key = current_app.config.get("GEMINI_API_KEY")
    if api_key:
        user_name = context.get("user_name") or "CampusOne user"
        prompt = (
            "You are CampusOne's concise campus assistant. Answer helpfully, but do not claim "
            "access to personal records unless they are included in the message. "
            f"User name: {user_name}. User role: {role}. Message: {message}"
        )
        model = current_app.config.get("GEMINI_MODEL", "gemini-2.5-flash")
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urlopen(req, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AssistantServiceError("Gemini request failed") from exc

        try:
            answer = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise AssistantServiceError("Gemini returned an invalid response") from exc
        if not answer:
            raise AssistantServiceError("Gemini returned an empty response")
        return answer

    if role == "student" and student_id:
        return answer_question(student_id, message)
    return "I can help with campus questions. Ask me about schedules, services, or campus procedures."
