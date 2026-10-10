from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import generate_password_hash
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.notify import notify_user
from utils.sla import sla_info

bp = Blueprint("admin", __name__)


@bp.route("/dashboard")
@role_required("admin")
def dashboard():
    counts = {
        "students": query_db("SELECT COUNT(*) c FROM students", one=True)["c"],
        "faculty": query_db("SELECT COUNT(*) c FROM faculty", one=True)["c"],
        "open_requests": query_db("SELECT COUNT(*) c FROM requests WHERE status NOT IN ('Resolved','Rejected')", one=True)["c"],
        "pending_leaves": query_db("SELECT COUNT(*) c FROM leave_requests WHERE status='Pending'", one=True)["c"],
        "unread_notices": query_db("SELECT COUNT(*) c FROM notices WHERE date(created_at) = date('now')", one=True)["c"],
    }
    today_entries = query_db("SELECT COUNT(*) c FROM entry_logs WHERE date(timestamp) = date('now')", one=True)["c"]
    counts["today_entries"] = today_entries

    total_rooms = query_db("SELECT COUNT(*) c FROM rooms", one=True)["c"]
    occupied_rooms = query_db("SELECT COUNT(*) c FROM rooms WHERE occupied > 0", one=True)["c"]
    counts["hostel_occupancy_pct"] = round((occupied_rooms / total_rooms) * 100, 1) if total_rooms else 0

    open_reqs = query_db("SELECT * FROM requests WHERE status NOT IN ('Resolved','Rejected') ORDER BY created_at")
    overdue = [r for r in open_reqs if sla_info(r["priority"], r["created_at"], r["status"])["overdue"]]

    by_category = query_db("SELECT category, COUNT(*) c FROM requests GROUP BY category ORDER BY c DESC")
    by_status = query_db("SELECT status, COUNT(*) c FROM requests GROUP BY status")
    by_priority = query_db("SELECT priority, COUNT(*) c FROM requests GROUP BY priority")

    att_overall = query_db(
        "SELECT SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) present, COUNT(*) total FROM attendance", one=True
    )
    att_pct = round((att_overall["present"] / att_overall["total"]) * 100, 1) if att_overall["total"] else 0

    below_threshold = query_db(
        "SELECT u.name, s.roll_number, "
        "ROUND(100.0 * SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct "
        "FROM attendance a JOIN students s ON a.student_id = s.id JOIN users u ON s.user_id = u.id "
        "GROUP BY a.student_id HAVING pct < 75 ORDER BY pct LIMIT 10"
    )

    # Recurring issue detection: same category+hostel-ish text repeated in last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    recurring = query_db(
        "SELECT category, COUNT(*) c FROM requests WHERE created_at >= ? GROUP BY category HAVING c >= 4 ORDER BY c DESC",
        (thirty_days_ago,),
    )

    return render_template("admin/dashboard.html", counts=counts, overdue=overdue, by_category=by_category,
                            by_status=by_status, by_priority=by_priority, att_pct=att_pct,
                            below_threshold=below_threshold, recurring=recurring)


@bp.route("/requests")
@role_required("admin")
def requests_view():
    status_filter = request.args.get("status", "")
    q = "SELECT r.*, u.name AS student_name, s.college_id FROM requests r " \
        "LEFT JOIN students s ON r.student_id = s.id LEFT JOIN users u ON s.user_id = u.id "
    args = ()
    if status_filter:
        q += "WHERE r.status = ? "
        args = (status_filter,)
    q += "ORDER BY r.created_at DESC"
    rows = query_db(q, args)
    enriched = []
    for r in rows:
        d = dict(r)
        d["sla"] = sla_info(r["priority"], r["created_at"], r["status"])
        enriched.append(d)
    return render_template("admin/requests.html", requests=enriched, status_filter=status_filter)


@bp.route("/requests/<int:rid>/delete", methods=["POST"])
@role_required("admin")
def delete_request(rid):
    verify_csrf()
    req = query_db("SELECT id, title FROM requests WHERE id = ?", (rid,), one=True)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.requests_view"))

    execute_db("DELETE FROM request_updates WHERE request_id = ?", (rid,))
    execute_db("DELETE FROM requests WHERE id = ?", (rid,))
    log_action(session["user_id"], "Request removed", "requests", rid, req["title"], None)
    flash("Request removed.", "success")
    return redirect(url_for("admin.requests_view"))


@bp.route("/requests/<int:rid>", methods=["GET", "POST"])
@role_required("admin")
def request_detail(rid):
    req = query_db(
        "SELECT r.*, u.name AS student_name, s.college_id FROM requests r "
        "LEFT JOIN students s ON r.student_id = s.id LEFT JOIN users u ON s.user_id = u.id WHERE r.id = ?",
        (rid,), one=True,
    )
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("admin.requests_view"))

    if request.method == "POST":
        verify_csrf()
        new_status = request.form.get("status")
        assigned_to = request.form.get("assigned_to", "")
        note = request.form.get("note", "")
        old_status = req["status"]
        execute_db(
            "UPDATE requests SET status = ?, assigned_to = ?, "
            "assigned_at = CASE WHEN ? != '' THEN datetime('now') ELSE assigned_at END, "
            "resolution_note = ?, updated_at = datetime('now') WHERE id = ?",
            (new_status, assigned_to, assigned_to, note, rid),
        )
        execute_db(
            "INSERT INTO request_updates (request_id, updated_by, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
            (rid, session["user_id"], old_status, new_status, note),
        )
        if new_status != old_status and req["student_id"]:
            stu = query_db("SELECT user_id FROM students WHERE id = ?", (req["student_id"],), one=True)
            if stu:
                notify_user(stu["user_id"], "request", f"Request update: {req['title']}",
                            f"Status changed to {new_status}.", url_for("student.request_detail", rid=rid))
        log_action(session["user_id"], "Request status changed", "requests", rid, old_status, new_status)
        flash("Request updated.", "success")
        return redirect(url_for("admin.request_detail", rid=rid))

    updates = query_db(
        "SELECT ru.*, u.name AS updated_by_name FROM request_updates ru LEFT JOIN users u ON ru.updated_by = u.id "
        "WHERE ru.request_id = ? ORDER BY ru.created_at", (rid,),
    )
    sla = sla_info(req["priority"], req["created_at"], req["status"])
    return render_template("admin/request_detail.html", req=req, updates=updates, sla=sla)


@bp.route("/users", methods=["GET", "POST"])
@role_required("admin")
def users():
    if request.method == "POST":
        verify_csrf()
        name = request.form.get("name")
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role")
        password = request.form.get("password")
        phone = request.form.get("phone", "")
        if query_db("SELECT id FROM users WHERE email = ?", (email,), one=True):
            flash("A user with that email already exists.", "error")
        else:
            uid = execute_db(
                "INSERT INTO users (email, password_hash, role, name, phone) VALUES (?, ?, ?, ?, ?)",
                (email, generate_password_hash(password), role, name, phone),
            )
            log_action(session["user_id"], "User created", "users", uid, None, f"{name} ({role})")
            flash(f"User {name} created as {role}.", "success")
        return redirect(url_for("admin.users"))

    rows = query_db("SELECT * FROM users ORDER BY role, name")
    return render_template("admin/users.html", users=rows)


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
@role_required("admin")
def toggle_user(uid):
    verify_csrf()
    user = query_db("SELECT * FROM users WHERE id = ?", (uid,), one=True)
    new_state = 0 if user["is_active"] else 1
    execute_db("UPDATE users SET is_active = ? WHERE id = ?", (new_state, uid))
    log_action(session["user_id"], "User activation toggled", "users", uid, user["is_active"], new_state)
    return redirect(url_for("admin.users"))


@bp.route("/notices", methods=["GET", "POST"])
@role_required("admin")
def notices():
    if request.method == "POST":
        verify_csrf()
        title = request.form.get("title")
        body = request.form.get("body", "")
        notice_type = request.form.get("notice_type", "General")
        target_audience = request.form.get("target_audience", "Everyone")
        target_value = request.form.get("target_value", "")
        requires_ack = 1 if request.form.get("requires_ack") else 0
        nid = execute_db(
            "INSERT INTO notices (title, body, notice_type, target_audience, target_value, requires_ack, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, body, notice_type, target_audience, target_value, requires_ack, session["user_id"]),
        )
        # Notify affected students
        if target_audience == "Everyone":
            students = query_db("SELECT user_id FROM students")
        elif target_audience == "Branch":
            students = query_db(
                "SELECT s.user_id FROM students s JOIN branches b ON s.branch_id = b.id WHERE b.code = ?",
                (target_value,))
        elif target_audience == "Hostel":
            students = query_db(
                "SELECT s.user_id FROM students s JOIN hostels h ON s.hostel_id = h.id WHERE h.name = ?",
                (target_value,))
        else:
            students = query_db("SELECT user_id FROM students")
        for s in students:
            notify_user(s["user_id"], "notice", f"New notice: {title}", body[:120], url_for("student.notices"))
        log_action(session["user_id"], "Notice created", "notices", nid, None, title)
        flash("Notice published.", "success")
        return redirect(url_for("admin.notices"))

    rows = query_db("SELECT * FROM notices ORDER BY created_at DESC")
    branches = query_db("SELECT code, name FROM branches")
    hostels = query_db("SELECT name FROM hostels")
    return render_template("admin/notices.html", notices=rows, branches=branches, hostels=hostels)


@bp.route("/attendance")
@role_required("admin")
def attendance():
    by_branch = query_db(
        "SELECT br.name AS branch, "
        "ROUND(100.0 * SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct "
        "FROM attendance a JOIN students s ON a.student_id = s.id JOIN branches br ON s.branch_id = br.id "
        "GROUP BY br.id ORDER BY pct"
    )
    by_subject = query_db(
        "SELECT sub.name AS subject, "
        "ROUND(100.0 * SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct "
        "FROM attendance a JOIN subjects sub ON a.subject_id = sub.id GROUP BY sub.id ORDER BY pct"
    )
    below_threshold = query_db(
        "SELECT u.name, s.roll_number, br.name AS branch, "
        "ROUND(100.0 * SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct "
        "FROM attendance a JOIN students s ON a.student_id = s.id JOIN users u ON s.user_id = u.id "
        "JOIN branches br ON s.branch_id = br.id GROUP BY a.student_id HAVING pct < 75 ORDER BY pct"
    )
    return render_template("admin/attendance.html", by_branch=by_branch, by_subject=by_subject,
                            below_threshold=below_threshold)


@bp.route("/audit")
@role_required("admin")
def audit():
    rows = query_db(
        "SELECT al.*, u.name AS user_name FROM audit_logs al LEFT JOIN users u ON al.user_id = u.id "
        "ORDER BY al.created_at DESC LIMIT 300"
    )
    return render_template("admin/audit.html", logs=rows)


@bp.route("/academics", methods=["GET", "POST"])
@role_required("admin")
def academics():
    if request.method == "POST":
        verify_csrf()
        action = request.form.get("action")
        if action == "add_department":
            name = request.form.get("name", "").strip()
            if name:
                did = execute_db("INSERT INTO departments (name) VALUES (?)", (name,))
                log_action(session["user_id"], "Department created", "departments", did, None, name)
                flash(f"Department '{name}' created.", "success")
        elif action == "add_branch":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip().upper()
            department_id = request.form.get("department_id")
            if name and code:
                bid = execute_db("INSERT INTO branches (name, code, department_id) VALUES (?, ?, ?)",
                                  (name, code, department_id))
                log_action(session["user_id"], "Branch created", "branches", bid, None, code)
                flash(f"Branch '{code}' created.", "success")
        elif action == "add_subject":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip().upper()
            branch_id = request.form.get("branch_id")
            semester = request.form.get("semester")
            if name and code:
                sid = execute_db("INSERT INTO subjects (name, code, branch_id, semester) VALUES (?, ?, ?, ?)",
                                  (name, code, branch_id, semester))
                log_action(session["user_id"], "Subject created", "subjects", sid, None, code)
                flash(f"Subject '{code}' created.", "success")
        elif action == "add_section":
            branch_id = request.form.get("branch_id")
            year = request.form.get("year")
            semester = request.form.get("semester")
            name = request.form.get("name", "").strip()
            if name:
                secid = execute_db(
                    "INSERT INTO sections (branch_id, year, semester, name) VALUES (?, ?, ?, ?)",
                    (branch_id, year, semester, name),
                )
                log_action(session["user_id"], "Section created", "sections", secid, None, name)
                flash(f"Section '{name}' created.", "success")
        elif action == "add_faculty":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            employee_id = request.form.get("employee_id", "").strip()
            department_id = request.form.get("department_id")
            designation = request.form.get("designation", "").strip()
            password = request.form.get("password", "").strip() or "faculty123"

            if not name or not email or not employee_id or not department_id:
                flash("Faculty name, email, employee ID, and department are required.", "error")
            elif query_db("SELECT id FROM users WHERE email = ?", (email,), one=True):
                flash("A user with that email already exists.", "error")
            elif query_db("SELECT id FROM faculty WHERE employee_id = ?", (employee_id,), one=True):
                flash("That employee ID is already assigned to another faculty member.", "error")
            else:
                uid = execute_db(
                    "INSERT INTO users (email, password_hash, role, name, phone) VALUES (?, ?, 'faculty', ?, ?)",
                    (email, generate_password_hash(password), name, phone),
                )
                fid = execute_db(
                    "INSERT INTO faculty (user_id, employee_id, department_id, designation) VALUES (?, ?, ?, ?)",
                    (uid, employee_id, department_id, designation),
                )
                log_action(session["user_id"], "Faculty created", "faculty", fid, None, f"{name} ({employee_id})")
                flash(f"Faculty '{name}' created successfully.", "success")
        return redirect(url_for("admin.academics"))

    departments = query_db("SELECT * FROM departments ORDER BY name")
    branches = query_db(
        "SELECT b.*, d.name AS department_name FROM branches b LEFT JOIN departments d ON b.department_id = d.id ORDER BY b.name"
    )
    faculty = query_db(
        "SELECT f.id, u.name, u.email, u.phone, f.employee_id, d.name AS department_name, f.designation "
        "FROM faculty f JOIN users u ON f.user_id = u.id LEFT JOIN departments d ON f.department_id = d.id "
        "ORDER BY u.name"
    )
    subjects = query_db(
        "SELECT s.*, b.code AS branch_code FROM subjects s LEFT JOIN branches b ON s.branch_id = b.id ORDER BY s.code"
    )
    sections = query_db(
        "SELECT sec.*, b.code AS branch_code FROM sections sec LEFT JOIN branches b ON sec.branch_id = b.id "
        "ORDER BY b.code, sec.year, sec.name"
    )
    mappings = query_db(
        "SELECT fs.id, u.name AS faculty_name, sub.name AS subject_name, sec.name AS section_name "
        "FROM faculty_subjects fs JOIN faculty f ON fs.faculty_id = f.id JOIN users u ON f.user_id = u.id "
        "JOIN subjects sub ON fs.subject_id = sub.id JOIN sections sec ON fs.section_id = sec.id "
        "ORDER BY u.name"
    )
    return render_template("admin/academics.html", departments=departments, branches=branches,
                            faculty=faculty, subjects=subjects, sections=sections, mappings=mappings)


@bp.route("/hostel", methods=["GET", "POST"])
@role_required("admin")
def hostel():
    if request.method == "POST":
        verify_csrf()
        action = request.form.get("action")
        if action == "add_hostel":
            name = request.form.get("name")
            block = request.form.get("block", "")
            capacity = request.form.get("capacity", 0)
            hid = execute_db("INSERT INTO hostels (name, block, capacity) VALUES (?, ?, ?)", (name, block, capacity))
            log_action(session["user_id"], "Hostel created", "hostels", hid, None, name)
            flash(f"Hostel '{name}' created.", "success")
        elif action == "add_room":
            hostel_id = request.form.get("hostel_id")
            room_number = request.form.get("room_number")
            capacity = request.form.get("room_capacity", 2)
            rid = execute_db(
                "INSERT INTO rooms (hostel_id, room_number, capacity, occupied, status) VALUES (?, ?, ?, 0, 'Available')",
                (hostel_id, room_number, capacity),
            )
            log_action(session["user_id"], "Room created", "rooms", rid, None, room_number)
            flash(f"Room '{room_number}' added.", "success")
        elif action == "allocate":
            college_id = request.form.get("college_id", "").strip()
            room_id = request.form.get("room_id")
            student = query_db("SELECT * FROM students WHERE college_id = ?", (college_id,), one=True)
            room = query_db("SELECT * FROM rooms WHERE id = ?", (room_id,), one=True)
            if not student:
                flash("No student found with that College ID.", "error")
            elif not room:
                flash("Room not found.", "error")
            elif room["occupied"] >= room["capacity"]:
                flash("That room is already full.", "error")
            else:
                old_room_id = student["room_id"]
                if old_room_id:
                    execute_db("UPDATE rooms SET occupied = MAX(occupied - 1, 0) WHERE id = ?", (old_room_id,))
                    execute_db("UPDATE hostel_allocations SET active = 0 WHERE student_id = ? AND active = 1",
                                (student["id"],))
                execute_db("UPDATE students SET hostel_id = ?, room_id = ? WHERE id = ?",
                            (room["hostel_id"], room_id, student["id"]))
                execute_db("UPDATE rooms SET occupied = occupied + 1 WHERE id = ?", (room_id,))
                execute_db("INSERT INTO hostel_allocations (student_id, room_id) VALUES (?, ?)",
                            (student["id"], room_id))
                execute_db(
                    "UPDATE rooms SET status = CASE WHEN occupied >= capacity THEN 'Full' WHEN occupied = 0 THEN "
                    "'Available' ELSE 'Partially Occupied' END WHERE id IN (?, ?)",
                    (room_id, old_room_id or room_id),
                )
                log_action(session["user_id"], "Student allocated to room", "students", student["id"],
                            old_room_id, room_id)
                flash(f"{student['college_id']} allocated to room {room['room_number']}.", "success")
        return redirect(url_for("admin.hostel"))

    hostels = query_db("SELECT * FROM hostels")
    rooms = query_db(
        "SELECT r.*, h.name AS hostel_name FROM rooms r JOIN hostels h ON r.hostel_id = h.id ORDER BY h.name, r.room_number"
    )
    return render_template("admin/hostel.html", hostels=hostels, rooms=rooms)


@bp.route("/exams", methods=["GET", "POST"])
@role_required("admin")
def exams():
    if request.method == "POST":
        verify_csrf()
        name = request.form.get("name")
        exam_type = request.form.get("exam_type")
        subject_id = request.form.get("subject_id")
        section_id = request.form.get("section_id")
        date = request.form.get("date")
        time = request.form.get("time")
        room = request.form.get("room")
        max_marks = request.form.get("max_marks", 100)
        eid = execute_db(
            "INSERT INTO exams (name, exam_type, subject_id, section_id, date, time, room, max_marks) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, exam_type, subject_id, section_id, date, time, room, max_marks),
        )
        students = query_db("SELECT user_id FROM students WHERE section_id = ?", (section_id,))
        for s in students:
            notify_user(s["user_id"], "exam", f"Exam scheduled: {name}", f"On {date} at {time}, Room {room}.",
                        url_for("student.exams"))
        log_action(session["user_id"], "Exam created", "exams", eid, None, name)
        flash("Exam scheduled.", "success")
        return redirect(url_for("admin.exams"))

    rows = query_db(
        "SELECT e.*, sub.name AS subject_name, sec.name AS section_name FROM exams e "
        "JOIN subjects sub ON e.subject_id = sub.id JOIN sections sec ON e.section_id = sec.id ORDER BY e.date"
    )
    subjects = query_db("SELECT id, name FROM subjects")
    sections = query_db("SELECT id, name FROM sections")
    return render_template("admin/exams.html", exams=rows, subjects=subjects, sections=sections)


@bp.route("/exams/<int:eid>/results", methods=["GET", "POST"])
@role_required("admin")
def exam_results(eid):
    exam = query_db("SELECT * FROM exams WHERE id = ?", (eid,), one=True)
    if request.method == "POST":
        verify_csrf()
        student_id = request.form.get("student_id")
        marks = request.form.get("marks_obtained")
        previous_result = query_db(
            "SELECT marks_obtained FROM results WHERE exam_id = ? AND student_id = ?",
            (eid, student_id), one=True,
        )
        execute_db(
            "INSERT INTO results (exam_id, student_id, marks_obtained) VALUES (?, ?, ?) "
            "ON CONFLICT(exam_id, student_id) DO UPDATE SET marks_obtained = excluded.marks_obtained",
            (eid, student_id, marks),
        )
        marks_changed = previous_result is None or previous_result["marks_obtained"] != marks
        if previous_result and previous_result["marks_obtained"] is not None:
            try:
                marks_changed = float(previous_result["marks_obtained"]) != float(marks)
            except (TypeError, ValueError):
                marks_changed = True
        if marks_changed:
            student = query_db("SELECT user_id FROM students WHERE id = ?", (student_id,), one=True)
            if student:
                notify_user(
                    student["user_id"], "exam", f"Result published: {exam['name']}",
                    f"Your marks: {marks} / {exam['max_marks']}.", url_for("student.exams"),
                )
        flash("Result saved.", "success")
        return redirect(url_for("admin.exam_results", eid=eid))

    students = query_db(
        "SELECT s.id, s.roll_number, u.name, r.marks_obtained FROM students s JOIN users u ON s.user_id = u.id "
        "LEFT JOIN results r ON r.student_id = s.id AND r.exam_id = ? WHERE s.section_id = ? ORDER BY s.roll_number",
        (eid, exam["section_id"]),
    )
    return render_template("admin/exam_results.html", exam=exam, students=students)


@bp.route("/timetable", methods=["GET", "POST"])
@role_required("admin")
def timetable():
    if request.method == "POST":
        verify_csrf()
        section_id = request.form.get("section_id")
        subject_id = request.form.get("subject_id")
        faculty_id = request.form.get("faculty_id")
        execute_db(
            "INSERT INTO timetable (section_id, subject_id, faculty_id, day_of_week, start_time, end_time, room) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (section_id, subject_id, faculty_id,
             request.form.get("day_of_week"), request.form.get("start_time"), request.form.get("end_time"),
             request.form.get("room")),
        )
        # Keep the faculty-subject mapping table in sync so it reflects who teaches what.
        existing_map = query_db(
            "SELECT id FROM faculty_subjects WHERE faculty_id = ? AND subject_id = ? AND section_id = ?",
            (faculty_id, subject_id, section_id), one=True,
        )
        if not existing_map:
            execute_db("INSERT INTO faculty_subjects (faculty_id, subject_id, section_id) VALUES (?, ?, ?)",
                        (faculty_id, subject_id, section_id))
        flash("Timetable entry added.", "success")
        return redirect(url_for("admin.timetable"))

    rows = query_db(
        "SELECT t.*, sub.name AS subject_name, sec.name AS section_name, u.name AS faculty_name FROM timetable t "
        "JOIN subjects sub ON t.subject_id = sub.id JOIN sections sec ON t.section_id = sec.id "
        "JOIN faculty f ON t.faculty_id = f.id JOIN users u ON f.user_id = u.id "
        "ORDER BY sec.name, t.day_of_week, t.start_time"
    )
    subjects = query_db("SELECT id, name FROM subjects")
    sections = query_db("SELECT id, name FROM sections")
    faculty_list = query_db("SELECT f.id, u.name FROM faculty f JOIN users u ON f.user_id = u.id")
    return render_template("admin/timetable.html", rows=rows, subjects=subjects, sections=sections,
                            faculty_list=faculty_list)
