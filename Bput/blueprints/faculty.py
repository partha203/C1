from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from utils.auth_utils import role_required, verify_csrf
from utils.db import query_db, execute_db
from utils.audit import log_action
from utils.notify import notify_user
from utils.uploads import save_upload

bp = Blueprint("faculty", __name__)


def get_faculty():
    return query_db("SELECT * FROM faculty WHERE user_id = ?", (session["user_id"],), one=True)


@bp.route("/dashboard")
@role_required("faculty")
def dashboard():
    fac = get_faculty()
    if not fac:
        flash("Faculty profile not found. Contact admin.", "error")
        return render_template("faculty/dashboard.html", classes=[], assignments=[])

    today_name = datetime.now().strftime("%A")
    classes = query_db(
        "SELECT t.*, sub.name AS subject_name, sec.name AS section_name, br.code AS branch_code "
        "FROM timetable t JOIN subjects sub ON t.subject_id = sub.id "
        "JOIN sections sec ON t.section_id = sec.id JOIN branches br ON sec.branch_id = br.id "
        "WHERE t.faculty_id = ? AND t.day_of_week = ? ORDER BY t.start_time",
        (fac["id"], today_name),
    )
    my_assignments = query_db(
        "SELECT a.*, sub.name AS subject_name, "
        "(SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = a.id) AS submitted_count "
        "FROM assignments a JOIN subjects sub ON a.subject_id = sub.id "
        "WHERE a.faculty_id = ? ORDER BY a.created_at DESC LIMIT 5",
        (fac["id"],),
    )
    return render_template("faculty/dashboard.html", classes=classes, assignments=my_assignments, faculty=fac)


@bp.route("/attendance", methods=["GET", "POST"])
@role_required("faculty")
def attendance():
    fac = get_faculty()
    my_classes = query_db(
        "SELECT t.subject_id, t.section_id, sub.name AS subject_name, sec.name AS section_name "
        "FROM timetable t JOIN subjects sub ON t.subject_id = sub.id JOIN sections sec ON t.section_id = sec.id "
        "WHERE t.faculty_id = ? GROUP BY t.subject_id, t.section_id", (fac["id"],),
    )

    subject_id = request.args.get("subject_id", type=int)
    section_id = request.args.get("section_id", type=int)
    date = request.args.get("date") or datetime.now().strftime("%Y-%m-%d")

    students = []
    existing = {}
    if subject_id and section_id:
        students = query_db(
            "SELECT s.id, s.college_id, s.roll_number, u.name FROM students s JOIN users u ON s.user_id = u.id "
            "WHERE s.section_id = ? ORDER BY s.roll_number", (section_id,),
        )
        rows = query_db(
            "SELECT student_id, status FROM attendance WHERE subject_id = ? AND date = ?", (subject_id, date),
        )
        existing = {r["student_id"]: r["status"] for r in rows}

    if request.method == "POST":
        verify_csrf()
        subject_id = request.form.get("subject_id", type=int)
        section_id = request.form.get("section_id", type=int)
        date = request.form.get("date")
        previous_statuses = {
            row["student_id"]: row["status"]
            for row in query_db(
                "SELECT student_id, status FROM attendance WHERE subject_id = ? AND date = ?",
                (subject_id, date),
            )
        }
        subject = query_db("SELECT name FROM subjects WHERE id = ?", (subject_id,), one=True)
        student_ids = query_db("SELECT id FROM students WHERE section_id = ?", (section_id,))
        for s in student_ids:
            status = request.form.get(f"status_{s['id']}", "Absent")
            execute_db(
                "INSERT INTO attendance (student_id, subject_id, section_id, faculty_id, date, status) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(student_id, subject_id, date) DO UPDATE SET status = excluded.status",
                (s["id"], subject_id, section_id, fac["id"], date, status),
            )
            if previous_statuses.get(s["id"]) != status:
                stu = query_db("SELECT user_id FROM students WHERE id = ?", (s["id"],), one=True)
                if stu:
                    notify_user(
                        stu["user_id"], "attendance", "Attendance updated",
                        f"Your attendance for {subject['name'] if subject else 'class'} on {date} was marked {status.lower()}.",
                        url_for("student.attendance"),
                    )
        log_action(session["user_id"], "Attendance modified", "attendance", subject_id, None, f"section {section_id} on {date}")
        flash("Attendance saved.", "success")
        return redirect(url_for("faculty.attendance", subject_id=subject_id, section_id=section_id, date=date))

    return render_template("faculty/attendance.html", my_classes=my_classes, students=students,
                            existing=existing, subject_id=subject_id, section_id=section_id, date=date)


@bp.route("/timetable")
@role_required("faculty")
def timetable():
    fac = get_faculty()
    rows = query_db(
        "SELECT t.*, sub.name AS subject_name, sec.name AS section_name FROM timetable t "
        "JOIN subjects sub ON t.subject_id = sub.id JOIN sections sec ON t.section_id = sec.id "
        "WHERE t.faculty_id = ? ORDER BY "
        "CASE day_of_week WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3 "
        "WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 ELSE 7 END, t.start_time",
        (fac["id"],),
    )
    return render_template("faculty/timetable.html", rows=rows)


@bp.route("/assignments", methods=["GET", "POST"])
@role_required("faculty")
def assignments():
    fac = get_faculty()
    sections = query_db(
        "SELECT DISTINCT sec.id, sec.name FROM timetable t JOIN sections sec ON t.section_id = sec.id "
        "WHERE t.faculty_id = ?", (fac["id"],),
    )
    subjects = query_db(
        "SELECT DISTINCT sub.id, sub.name FROM timetable t JOIN subjects sub ON t.subject_id = sub.id "
        "WHERE t.faculty_id = ?", (fac["id"],),
    )
    if request.method == "POST":
        verify_csrf()
        title = request.form.get("title")
        subject_id = request.form.get("subject_id")
        section_id = request.form.get("section_id")
        deadline = request.form.get("deadline")
        description = request.form.get("description", "")
        max_marks = request.form.get("max_marks", 100)
        attachment = save_upload(request.files.get("attachment"), "assignments",
                                  current_app.config["ALLOWED_DOC_EXT"], current_app.config["UPLOAD_FOLDER"])
        execute_db(
            "INSERT INTO assignments (faculty_id, subject_id, section_id, title, description, deadline, attachment, max_marks) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fac["id"], subject_id, section_id, title, description, deadline, attachment, max_marks),
        )
        section_students = query_db("SELECT user_id FROM students WHERE section_id = ?", (section_id,))
        for s in section_students:
            notify_user(s["user_id"], "assignment", "New assignment", f"'{title}' has been posted.",
                        url_for("student.assignments"))
        flash("Assignment created.", "success")
        return redirect(url_for("faculty.assignments"))

    my_assignments = query_db(
        "SELECT a.*, sub.name AS subject_name, sec.name AS section_name FROM assignments a "
        "JOIN subjects sub ON a.subject_id = sub.id JOIN sections sec ON a.section_id = sec.id "
        "WHERE a.faculty_id = ? ORDER BY a.created_at DESC", (fac["id"],),
    )
    return render_template("faculty/assignments.html", assignments=my_assignments, sections=sections, subjects=subjects)


@bp.route("/assignments/<int:aid>/submissions", methods=["GET", "POST"])
@role_required("faculty")
def submissions(aid):
    assignment = query_db("SELECT * FROM assignments WHERE id = ?", (aid,), one=True)
    if request.method == "POST":
        verify_csrf()
        sub_id = request.form.get("submission_id")
        marks = request.form.get("marks_obtained")
        feedback = request.form.get("feedback", "")
        submission = query_db(
            "SELECT student_id, marks_obtained FROM assignment_submissions WHERE id = ? AND assignment_id = ?",
            (sub_id, aid), one=True,
        )
        execute_db("UPDATE assignment_submissions SET marks_obtained = ?, feedback = ? WHERE id = ? AND assignment_id = ?",
                    (marks, feedback, sub_id, aid))
        marks_changed = bool(submission and submission["marks_obtained"] is None)
        if submission and submission["marks_obtained"] is not None:
            try:
                marks_changed = float(submission["marks_obtained"]) != float(marks)
            except (TypeError, ValueError):
                marks_changed = True
        if marks_changed and assignment:
            student = query_db("SELECT user_id FROM students WHERE id = ?", (submission["student_id"],), one=True)
            if student:
                notify_user(
                    student["user_id"], "assignment", f"Assignment graded: {assignment['title']}",
                    f"Your marks: {marks} / {assignment['max_marks']}." + (f" Feedback: {feedback}" if feedback else ""),
                    url_for("student.assignments"),
                )
        flash("Grading saved.", "success")
        return redirect(url_for("faculty.submissions", aid=aid))

    subs = query_db(
        "SELECT s.*, st.roll_number, u.name FROM assignment_submissions s "
        "JOIN students st ON s.student_id = st.id JOIN users u ON st.user_id = u.id "
        "WHERE s.assignment_id = ? ORDER BY u.name", (aid,),
    )
    return render_template("faculty/submissions.html", assignment=assignment, subs=subs)
