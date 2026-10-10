from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.notify import notify_user
from utils.sla import sla_info

bp = Blueprint("warden", __name__)


@bp.route("/dashboard")
@role_required("warden")
def dashboard():
    total_students = query_db("SELECT COUNT(*) c FROM students WHERE hostel_id IS NOT NULL", one=True)["c"]
    total_rooms = query_db("SELECT COUNT(*) c FROM rooms", one=True)["c"]
    occupied_rooms = query_db("SELECT COUNT(*) c FROM rooms WHERE occupied >= capacity", one=True)["c"]
    vacant_rooms = query_db("SELECT COUNT(*) c FROM rooms WHERE occupied < capacity", one=True)["c"]
    open_complaints = query_db(
        "SELECT COUNT(*) c FROM requests WHERE category = 'Hostel' AND status NOT IN ('Resolved','Rejected')",
        one=True,
    )["c"]
    pending_leaves = query_db("SELECT COUNT(*) c FROM leave_requests WHERE status = 'Pending'", one=True)["c"]

    recent_complaints = query_db(
        "SELECT r.*, u.name AS student_name FROM requests r JOIN students s ON r.student_id = s.id "
        "JOIN users u ON s.user_id = u.id WHERE r.category = 'Hostel' ORDER BY r.created_at DESC LIMIT 8"
    )
    return render_template("warden/dashboard.html", total_students=total_students, total_rooms=total_rooms,
                            occupied_rooms=occupied_rooms, vacant_rooms=vacant_rooms,
                            open_complaints=open_complaints, pending_leaves=pending_leaves,
                            recent_complaints=recent_complaints)


@bp.route("/complaints")
@role_required("warden")
def complaints():
    rows = query_db(
        "SELECT r.*, u.name AS student_name, s.college_id FROM requests r JOIN students s ON r.student_id = s.id "
        "JOIN users u ON s.user_id = u.id WHERE r.category = 'Hostel' ORDER BY r.created_at DESC"
    )
    enriched = []
    for r in rows:
        d = dict(r)
        d["sla"] = sla_info(r["priority"], r["created_at"], r["status"])
        enriched.append(d)
    return render_template("warden/complaints.html", requests=enriched)


@bp.route("/complaints/<int:rid>", methods=["GET", "POST"])
@role_required("warden")
def complaint_detail(rid):
    req = query_db(
        "SELECT r.*, u.name AS student_name, s.college_id FROM requests r JOIN students s ON r.student_id = s.id "
        "JOIN users u ON s.user_id = u.id WHERE r.id = ?", (rid,), one=True,
    )
    if request.method == "POST":
        verify_csrf()
        new_status = request.form.get("status")
        note = request.form.get("note", "")
        old_status = req["status"]
        execute_db(
            "UPDATE requests SET status = ?, resolution_note = ?, updated_at = datetime('now'), "
            "assigned_to = 'Warden', assigned_at = COALESCE(assigned_at, datetime('now')) WHERE id = ?",
            (new_status, note, rid),
        )
        execute_db(
            "INSERT INTO request_updates (request_id, updated_by, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
            (rid, session["user_id"], old_status, new_status, note),
        )
        if new_status != old_status:
            stu = query_db("SELECT user_id FROM students WHERE id = ?", (req["student_id"],), one=True)
            if stu:
                notify_user(stu["user_id"], "hostel", f"Complaint update: {req['title']}", f"Status: {new_status}",
                            url_for("student.request_detail", rid=rid))
        log_action(session["user_id"], "Request status changed", "requests", rid, old_status, new_status)
        flash("Complaint updated.", "success")
        return redirect(url_for("warden.complaint_detail", rid=rid))

    updates = query_db(
        "SELECT ru.*, u.name AS updated_by_name FROM request_updates ru LEFT JOIN users u ON ru.updated_by = u.id "
        "WHERE ru.request_id = ? ORDER BY ru.created_at", (rid,),
    )
    return render_template("warden/complaint_detail.html", req=req, updates=updates)


@bp.route("/leave-requests", methods=["GET", "POST"])
@role_required("warden")
def leave_requests():
    if request.method == "POST":
        verify_csrf()
        lid = request.form.get("leave_id")
        decision = request.form.get("decision")
        lr = query_db("SELECT * FROM leave_requests WHERE id = ?", (lid,), one=True)
        execute_db(
            "UPDATE leave_requests SET status = ?, reviewed_by = ?, reviewed_at = datetime('now') WHERE id = ?",
            (decision, session["user_id"], lid),
        )
        stu = query_db("SELECT user_id FROM students WHERE id = ?", (lr["student_id"],), one=True)
        notify_user(stu["user_id"], "leave", f"Leave request {decision}",
                    f"Your {lr['leave_type']} leave ({lr['start_date']} to {lr['end_date']}) was {decision.lower()}.",
                    url_for("student.leave"))
        log_action(session["user_id"], "Leave decision", "leave_requests", lid, "Pending", decision)
        flash(f"Leave {decision.lower()}.", "success")
        return redirect(url_for("warden.leave_requests"))

    rows = query_db(
        "SELECT lr.*, u.name AS student_name, s.college_id FROM leave_requests lr "
        "JOIN students s ON lr.student_id = s.id JOIN users u ON s.user_id = u.id ORDER BY lr.created_at DESC"
    )
    return render_template("warden/leave_requests.html", leaves=rows)


@bp.route("/rooms")
@role_required("warden")
def rooms():
    hostels = query_db("SELECT * FROM hostels")
    room_rows = query_db(
        "SELECT r.*, h.name AS hostel_name FROM rooms r JOIN hostels h ON r.hostel_id = h.id "
        "ORDER BY h.name, r.room_number"
    )
    return render_template("warden/rooms.html", hostels=hostels, rooms=room_rows)
