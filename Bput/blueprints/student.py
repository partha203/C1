from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.notify import notify_user
from utils.uploads import save_upload
from utils.ai_assistant import answer_question

bp = Blueprint("student", __name__)


def get_student():
    return query_db("SELECT * FROM students WHERE user_id = ?", (session["user_id"],), one=True)


@bp.route("/dashboard")
@role_required("student")
def dashboard():
    st = get_student()
    if not st:
        flash("Student profile not found. Contact admin.", "error")
        return render_template("student/dashboard.html", stats=None)

    att_rows = query_db(
        "SELECT SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS present, COUNT(*) AS total "
        "FROM attendance WHERE student_id = ?", (st["id"],), one=True,
    )
    total = att_rows["total"] or 0
    present = att_rows["present"] or 0
    pct = round((present / total) * 100, 1) if total else 0

    today_name = datetime.now().strftime("%A")
    today_classes = query_db(
        "SELECT t.start_time, t.end_time, sub.name AS subject, t.room, u.name AS faculty_name "
        "FROM timetable t JOIN subjects sub ON t.subject_id = sub.id "
        "JOIN faculty f ON t.faculty_id = f.id JOIN users u ON f.user_id = u.id "
        "WHERE t.section_id = ? AND t.day_of_week = ? ORDER BY t.start_time",
        (st["section_id"], today_name),
    )

    notices = query_db(
        "SELECT * FROM notices WHERE target_audience = 'Everyone' OR "
        "(target_audience = 'Branch' AND target_value = (SELECT code FROM branches WHERE id = ?)) OR "
        "(target_audience = 'Hostel' AND target_value = (SELECT name FROM hostels WHERE id = ?)) "
        "ORDER BY created_at DESC LIMIT 5",
        (st["branch_id"], st["hostel_id"]),
    )

    notifications = query_db(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 6", (session["user_id"],)
    )
    unread_count = query_db(
        "SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (session["user_id"],), one=True
    )["c"]

    pending_requests = query_db(
        "SELECT COUNT(*) AS c FROM requests WHERE student_id = ? AND status NOT IN ('Resolved','Rejected')",
        (st["id"],), one=True,
    )["c"]

    hostel = query_db("SELECT * FROM hostels WHERE id = ?", (st["hostel_id"],), one=True)
    room = query_db("SELECT * FROM rooms WHERE id = ?", (st["room_id"],), one=True)

    today_menu = query_db("SELECT meal, items FROM mess_menus WHERE day_of_week = ? ORDER BY meal", (today_name,))

    recent_entries = query_db(
        "SELECT * FROM entry_logs WHERE student_id = ? ORDER BY timestamp DESC LIMIT 3", (st["id"],)
    )

    upcoming_exams = query_db(
        "SELECT e.*, sub.name AS subject FROM exams e JOIN subjects sub ON e.subject_id = sub.id "
        "WHERE e.section_id = ? AND e.date >= ? ORDER BY e.date LIMIT 3",
        (st["section_id"], datetime.now().strftime("%Y-%m-%d")),
    )

    low_attendance = pct < 75 and total > 0

    stats = {
        "attendance_pct": pct, "present": present, "total": total,
        "today_classes": today_classes, "notices": notices,
        "notifications": notifications, "unread_count": unread_count,
        "pending_requests": pending_requests, "hostel": hostel, "room": room,
        "today_menu": today_menu, "recent_entries": recent_entries,
        "upcoming_exams": upcoming_exams, "low_attendance": low_attendance,
        "student": st,
    }
    return render_template("student/dashboard.html", stats=stats)


@bp.route("/attendance")
@role_required("student")
def attendance():
    st = get_student()
    rows = query_db(
        "SELECT sub.name AS subject, "
        "SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present, COUNT(*) AS total "
        "FROM attendance a JOIN subjects sub ON a.subject_id = sub.id "
        "WHERE a.student_id = ? GROUP BY a.subject_id ORDER BY sub.name", (st["id"],),
    )
    subject_stats = []
    for r in rows:
        p = round((r["present"] / r["total"]) * 100, 1) if r["total"] else 0
        subject_stats.append({"subject": r["subject"], "present": r["present"], "total": r["total"], "pct": p})

    history = query_db(
        "SELECT a.date, sub.name AS subject, a.status FROM attendance a "
        "JOIN subjects sub ON a.subject_id = sub.id WHERE a.student_id = ? ORDER BY a.date DESC LIMIT 60",
        (st["id"],),
    )
    return render_template("student/attendance.html", subject_stats=subject_stats, history=history)


@bp.route("/requests", methods=["GET", "POST"])
@role_required("student", "faculty", "admin", "warden", "mess", "frontdesk")
def requests_view():
    current_role = session.get("role")
    st = get_student() if current_role == "student" else None

    if request.method == "POST":
        verify_csrf()
        title = request.form.get("title", "").strip()
        category = request.form.get("category")
        priority = request.form.get("priority", "Normal")
        description = request.form.get("description", "")
        if not title or not category:
            flash("Title and category are required.", "error")
            return redirect(url_for("student.requests_view"))

        student_id = None
        if current_role == "student":
            student_id = st["id"] if st else None
        else:
            raw_student = (request.form.get("student_id") or "").strip()
            if raw_student:
                student_record = query_db(
                    "SELECT id FROM students WHERE college_id = ? OR id = ? LIMIT 1",
                    (raw_student, raw_student),
                    one=True,
                )
                if student_record:
                    student_id = student_record["id"]

        photo_path = save_upload(request.files.get("photo"), "requests",
                                  current_app.config["ALLOWED_IMAGE_EXT"], current_app.config["UPLOAD_FOLDER"])
        video_path = save_upload(request.files.get("video"), "requests",
                                  current_app.config["ALLOWED_VIDEO_EXT"], current_app.config["UPLOAD_FOLDER"],
                                  max_bytes=25 * 1024 * 1024)

        rid = execute_db(
            "INSERT INTO requests (student_id, title, description, category, priority, photo, video, created_by_role) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (student_id, title, description, category, priority, photo_path, video_path, current_role),
        )
        log_action(session["user_id"], "Request created", "requests", rid, None, title)
        flash("Request submitted successfully.", "success")
        return redirect(url_for("student.requests_view"))

    if current_role == "student":
        my_requests = query_db(
            "SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC", (st["id"],)
        )
    else:
        my_requests = query_db(
            "SELECT * FROM requests WHERE created_by_role = ? ORDER BY created_at DESC", (current_role,)
        )
    return render_template("student/requests.html", requests=my_requests, current_role=current_role)


@bp.route("/requests/<int:rid>")
@role_required("student", "faculty", "admin", "warden", "mess", "frontdesk")
def request_detail(rid):
    current_role = session.get("role")
    if current_role == "student":
        st = get_student()
        req = query_db("SELECT * FROM requests WHERE id = ? AND student_id = ?", (rid, st["id"]), one=True)
    else:
        req = query_db("SELECT * FROM requests WHERE id = ? AND created_by_role = ?", (rid, current_role), one=True)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("student.requests_view"))
    updates = query_db(
        "SELECT ru.*, u.name AS updated_by_name FROM request_updates ru "
        "LEFT JOIN users u ON ru.updated_by = u.id WHERE ru.request_id = ? ORDER BY ru.created_at",
        (rid,),
    )
    return render_template("student/request_detail.html", req=req, updates=updates)


@bp.route("/hostel")
@role_required("student")
def hostel():
    st = get_student()
    hostel = query_db("SELECT * FROM hostels WHERE id = ?", (st["hostel_id"],), one=True)
    room = query_db("SELECT * FROM rooms WHERE id = ?", (st["room_id"],), one=True)
    roommates = query_db(
        "SELECT u.name, s.roll_number FROM students s JOIN users u ON s.user_id = u.id "
        "WHERE s.room_id = ? AND s.id != ?", (st["room_id"], st["id"]),
    )
    return render_template("student/hostel.html", hostel=hostel, room=room, roommates=roommates)


@bp.route("/mess", methods=["GET", "POST"])
@role_required("student")
def mess():
    st = get_student()
    if request.method == "POST":
        verify_csrf()
        meal = request.form.get("meal")
        rating = request.form.get("rating")
        comment = request.form.get("comment", "")
        execute_db(
            "INSERT INTO mess_feedback (student_id, meal, rating, comment) VALUES (?, ?, ?, ?)",
            (st["id"], meal, rating, comment),
        )
        flash("Thanks for your feedback!", "success")
        return redirect(url_for("student.mess"))

    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    menu_rows = query_db("SELECT * FROM mess_menus ORDER BY day_of_week, meal")
    weekly = {d: [] for d in days_order}
    for r in menu_rows:
        weekly.setdefault(r["day_of_week"], []).append(r)
    today_name = datetime.now().strftime("%A")
    return render_template("student/mess.html", weekly=weekly, days_order=days_order, today_name=today_name)


@bp.route("/notices")
@role_required("student")
def notices():
    st = get_student()
    all_notices = query_db(
        "SELECT n.*, r.read_at, r.acknowledged_at FROM notices n "
        "LEFT JOIN notice_receipts r ON r.notice_id = n.id AND r.student_id = ? "
        "WHERE n.target_audience = 'Everyone' OR "
        "(n.target_audience = 'Branch' AND n.target_value = (SELECT code FROM branches WHERE id = ?)) OR "
        "(n.target_audience = 'Hostel' AND n.target_value = (SELECT name FROM hostels WHERE id = ?)) "
        "ORDER BY n.created_at DESC",
        (st["id"], st["branch_id"], st["hostel_id"]),
    )
    return render_template("student/notices.html", notices=all_notices)


@bp.route("/notices/<int:nid>/read", methods=["POST"])
@role_required("student")
def mark_notice_read(nid):
    st = get_student()
    existing = query_db("SELECT * FROM notice_receipts WHERE notice_id = ? AND student_id = ?",
                         (nid, st["id"]), one=True)
    if existing:
        execute_db("UPDATE notice_receipts SET read_at = datetime('now') WHERE id = ?", (existing["id"],))
    else:
        execute_db("INSERT INTO notice_receipts (notice_id, student_id, read_at) VALUES (?, ?, datetime('now'))",
                    (nid, st["id"]))
    return redirect(url_for("student.notices"))


@bp.route("/notices/<int:nid>/acknowledge", methods=["POST"])
@role_required("student")
def acknowledge_notice(nid):
    st = get_student()
    existing = query_db("SELECT * FROM notice_receipts WHERE notice_id = ? AND student_id = ?",
                         (nid, st["id"]), one=True)
    if existing:
        execute_db("UPDATE notice_receipts SET read_at = COALESCE(read_at, datetime('now')), "
                    "acknowledged_at = datetime('now') WHERE id = ?", (existing["id"],))
    else:
        execute_db("INSERT INTO notice_receipts (notice_id, student_id, read_at, acknowledged_at) "
                    "VALUES (?, ?, datetime('now'), datetime('now'))", (nid, st["id"]))
    flash("Notice acknowledged.", "success")
    return redirect(url_for("student.notices"))


@bp.route("/notifications")
@role_required("student")
def notifications():
    rows = query_db("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],))
    execute_db("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (session["user_id"],))
    return render_template("student/notifications.html", notifications=rows)


@bp.route("/entry-history")
@role_required("student")
def entry_history():
    st = get_student()
    rows = query_db("SELECT * FROM entry_logs WHERE student_id = ? ORDER BY timestamp DESC LIMIT 100", (st["id"],))
    return render_template("student/entry_history.html", entries=rows)


@bp.route("/assignments", methods=["GET", "POST"])
@role_required("student")
def assignments():
    st = get_student()
    if request.method == "POST":
        verify_csrf()
        aid = request.form.get("assignment_id")
        file_path = save_upload(request.files.get("file"), "assignments",
                                 current_app.config["ALLOWED_DOC_EXT"], current_app.config["UPLOAD_FOLDER"])
        if not file_path:
            flash("Please attach a valid file (pdf, jpg, png, docx, under 15MB).", "error")
            return redirect(url_for("student.assignments"))
        existing = query_db("SELECT * FROM assignment_submissions WHERE assignment_id = ? AND student_id = ?",
                             (aid, st["id"]), one=True)
        if existing:
            execute_db("UPDATE assignment_submissions SET file_path = ?, submitted_at = datetime('now') WHERE id = ?",
                        (file_path, existing["id"]))
        else:
            execute_db(
                "INSERT INTO assignment_submissions (assignment_id, student_id, file_path) VALUES (?, ?, ?)",
                (aid, st["id"], file_path),
            )
        flash("Assignment submitted.", "success")
        return redirect(url_for("student.assignments"))

    rows = query_db(
        "SELECT a.*, sub.name AS subject_name, u.name AS faculty_name, "
        "sub2.file_path AS my_file, sub2.marks_obtained, sub2.feedback, sub2.submitted_at "
        "FROM assignments a JOIN subjects sub ON a.subject_id = sub.id "
        "JOIN faculty f ON a.faculty_id = f.id JOIN users u ON f.user_id = u.id "
        "LEFT JOIN assignment_submissions sub2 ON sub2.assignment_id = a.id AND sub2.student_id = ? "
        "WHERE a.section_id = ? ORDER BY a.deadline",
        (st["id"], st["section_id"]),
    )
    return render_template("student/assignments.html", assignments=rows)


@bp.route("/exams")
@role_required("student")
def exams():
    st = get_student()
    upcoming = query_db(
        "SELECT e.*, sub.name AS subject FROM exams e JOIN subjects sub ON e.subject_id = sub.id "
        "WHERE e.section_id = ? ORDER BY e.date", (st["section_id"],),
    )
    results = query_db(
        "SELECT e.name AS exam_name, sub.name AS subject, e.max_marks, r.marks_obtained "
        "FROM results r JOIN exams e ON r.exam_id = e.id JOIN subjects sub ON e.subject_id = sub.id "
        "WHERE r.student_id = ? ORDER BY e.date DESC", (st["id"],),
    )
    total_obtained = sum(r["marks_obtained"] or 0 for r in results)
    total_max = sum(r["max_marks"] or 0 for r in results)
    overall_pct = round((total_obtained / total_max) * 100, 1) if total_max else None
    # Simple 10-point GPA approximation from overall percentage (percentage / 9.5, capped at 10)
    gpa = round(min(overall_pct / 9.5, 10), 2) if overall_pct is not None else None
    return render_template("student/exams.html", upcoming=upcoming, results=results, overall_pct=overall_pct, gpa=gpa)


@bp.route("/leave", methods=["GET", "POST"])
@role_required("student")
def leave():
    st = get_student()
    if request.method == "POST":
        verify_csrf()
        leave_type = request.form.get("leave_type")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        reason = request.form.get("reason", "")
        doc_path = save_upload(request.files.get("document"), "leave",
                                current_app.config["ALLOWED_DOC_EXT"], current_app.config["UPLOAD_FOLDER"])
        if not (leave_type and start_date and end_date):
            flash("Please fill all required fields.", "error")
            return redirect(url_for("student.leave"))
        lid = execute_db(
            "INSERT INTO leave_requests (student_id, leave_type, start_date, end_date, reason, document) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (st["id"], leave_type, start_date, end_date, reason, doc_path),
        )
        log_action(session["user_id"], "Leave requested", "leave_requests", lid)
        flash("Leave request submitted for approval.", "success")
        return redirect(url_for("student.leave"))

    my_leaves = query_db("SELECT * FROM leave_requests WHERE student_id = ? ORDER BY created_at DESC", (st["id"],))
    return render_template("student/leave.html", leaves=my_leaves)


@bp.route("/assistant", methods=["GET", "POST"])
@role_required("student")
def assistant():
    st = get_student()
    answer = None
    question = None
    if request.method == "POST":
        verify_csrf()
        question = request.form.get("question", "")
        answer = answer_question(st["id"], question)
    return render_template("student/assistant.html", answer=answer, question=question)
