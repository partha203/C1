from datetime import datetime
from flask import current_app


def compute_age_hours(created_at_str):
    try:
        created = datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return 0
    delta = datetime.now() - created
    return round(delta.total_seconds() / 3600, 1)


def sla_info(priority, created_at_str, status):
    sla_hours = current_app.config["SLA_HOURS"].get(priority, 48)
    age_hours = compute_age_hours(created_at_str)
    closed = status in ("Resolved", "Rejected")
    overdue = (age_hours > sla_hours) and not closed
    return {
        "age_hours": age_hours,
        "sla_hours": sla_hours,
        "overdue": overdue,
    }
