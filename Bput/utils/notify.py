"""
Notification abstraction for CampusOne.

Core in-app notifications always work with zero external configuration.
Email is sent through SMTP when EMAIL_* environment variables are set; otherwise
email delivery is skipped and the app keeps working normally.
WhatsApp is a status-only abstraction (Not configured / Queued / Sent / Failed)
ready to be wired up to a real provider later.
"""
import smtplib
from email.mime.text import MIMEText
from flask import current_app
from utils.db import execute_db, query_db


def notify_user(user_id, ntype, title, body, link=None):
    """Create an in-app notification and email the user when SMTP is configured."""
    try:
        execute_db(
            "INSERT INTO notifications (user_id, ntype, title, body, link) VALUES (?, ?, ?, ?, ?)",
            (user_id, ntype, title, body, link),
        )
    except Exception:
        pass

    try:
        user = query_db("SELECT email FROM users WHERE id = ?", (user_id,), one=True)
        if user and user["email"]:
            status = send_email(user["email"], title, body)
            if status != "Sent":
                current_app.logger.warning("Email notification for user %s: %s", user_id, status)
    except Exception:
        current_app.logger.exception("Could not send email notification for user %s", user_id)


def send_email(to_email, subject, body):
    """Best-effort email send. Returns a status string, never raises."""
    cfg = current_app.config
    if not (cfg.get("EMAIL_HOST") and cfg.get("EMAIL_USERNAME") and cfg.get("EMAIL_PASSWORD")):
        return "Not configured"
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = cfg.get("EMAIL_FROM") or cfg.get("EMAIL_USERNAME")
        msg["To"] = to_email
        port = int(cfg.get("EMAIL_PORT") or 587)
        smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp_class(cfg["EMAIL_HOST"], port, timeout=8) as server:
            if port != 465:
                server.starttls()
            server.login(cfg["EMAIL_USERNAME"], cfg["EMAIL_PASSWORD"])
            server.sendmail(msg["From"], [to_email], msg.as_string())
        return "Sent"
    except Exception:
        current_app.logger.exception("SMTP email delivery failed")
        return "Failed"


def send_whatsapp(to_phone, message):
    """Status-only WhatsApp abstraction. No paid API required for core app."""
    cfg = current_app.config
    if not (cfg.get("WHATSAPP_API_TOKEN") and cfg.get("WHATSAPP_PHONE_ID")):
        return "Not configured"
    # Real integration point for a WhatsApp Business API provider would go here.
    return "Queued"
