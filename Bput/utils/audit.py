from utils.db import execute_db


def log_action(user_id, action, entity=None, entity_id=None, old_value=None, new_value=None):
    try:
        execute_db(
            "INSERT INTO audit_logs (user_id, action, entity, entity_id, old_value, new_value) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, entity, entity_id,
             str(old_value) if old_value is not None else None,
             str(new_value) if new_value is not None else None),
        )
    except Exception:
        # Audit logging must never break the main request
        pass
