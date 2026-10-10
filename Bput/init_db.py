"""
CampusOne database initializer & demo data seeder.

Usage:
    python init_db.py            # creates schema + seeds demo data (safe to re-run; wipes and rebuilds)
"""
import os
import sqlite3
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "campusone.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

FIRST_NAMES = ["Aarav", "Ananya", "Rohit", "Priya", "Vikram", "Sneha", "Arjun", "Divya", "Karan", "Isha",
               "Rahul", "Neha", "Aditya", "Pooja", "Siddharth", "Kavya", "Manish", "Riya", "Suresh", "Anjali",
               "Nikhil", "Meera", "Abhishek", "Sanya", "Varun", "Tanvi", "Gaurav", "Shreya", "Amit", "Pallavi"]
LAST_NAMES = ["Sharma", "Patel", "Nayak", "Das", "Mohanty", "Singh", "Reddy", "Behera", "Panda", "Rout",
              "Sahoo", "Mishra", "Kumar", "Gupta", "Jena", "Pattnaik", "Sahu", "Swain", "Verma", "Hota"]


def rand_name(used):
    while True:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used:
            used.add(name)
            return name


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    cur = conn.cursor()

    # ---------------- Departments & Branches ----------------
    departments = [
        "Computer Science & Engineering", "Electronics & Communication Engineering",
        "Electrical Engineering", "Mechanical Engineering", "Civil Engineering",
    ]
    dept_ids = {}
    for d in departments:
        cur.execute("INSERT INTO departments (name) VALUES (?)", (d,))
        dept_ids[d] = cur.lastrowid

    branches = [
        ("Computer Science & Engineering", "CSE", departments[0]),
        ("Electronics & Communication Engineering", "ECE", departments[1]),
        ("Electrical Engineering", "EE", departments[2]),
        ("Mechanical Engineering", "ME", departments[3]),
        ("Civil Engineering", "CE", departments[4]),
    ]
    branch_ids = {}
    for name, code, dept in branches:
        cur.execute("INSERT INTO branches (name, code, department_id) VALUES (?, ?, ?)", (name, code, dept_ids[dept]))
        branch_ids[code] = cur.lastrowid

    # ---------------- Sections ----------------
    cse_id = branch_ids["CSE"]
    section_ids = {}
    for (branch_code, year, sem, sec_name) in [
        ("CSE", 3, 5, "CSE-3A"), ("CSE", 3, 5, "CSE-3B"),
        ("CSE", 2, 3, "CSE-2A"), ("ECE", 3, 5, "ECE-3A"),
        ("ME", 2, 3, "ME-2A"),
    ]:
        cur.execute("INSERT INTO sections (branch_id, year, semester, name) VALUES (?, ?, ?, ?)",
                    (branch_ids[branch_code], year, sem, sec_name))
        section_ids[sec_name] = cur.lastrowid

    # ---------------- Subjects ----------------
    subjects = [
        ("Database Management Systems", "CSE501", "CSE", 5),
        ("Operating Systems", "CSE502", "CSE", 5),
        ("Computer Networks", "CSE503", "CSE", 5),
        ("Software Engineering", "CSE504", "CSE", 5),
        ("Data Structures", "CSE301", "CSE", 3),
        ("Digital Electronics", "ECE501", "ECE", 5),
        ("Thermodynamics", "ME301", "ME", 3),
    ]
    subject_ids = {}
    for name, code, branch_code, sem in subjects:
        cur.execute("INSERT INTO subjects (name, code, branch_id, semester) VALUES (?, ?, ?, ?)",
                    (name, code, branch_ids[branch_code], sem))
        subject_ids[code] = cur.lastrowid

    # ---------------- Hostels & Rooms ----------------
    hostels = [("Boys Hostel A", "A", 200), ("Boys Hostel B", "B", 180), ("Girls Hostel C", "C", 150)]
    hostel_ids = {}
    hostel_blocks = {}
    for name, block, cap in hostels:
        cur.execute("INSERT INTO hostels (name, block, capacity) VALUES (?, ?, ?)", (name, block, cap))
        hostel_ids[name] = cur.lastrowid
        hostel_blocks[name] = block

    # room_ids is keyed by (hostel_name, room_number) to avoid collisions between
    # hostels that would otherwise share the same block-letter/number combination.
    room_ids = {}
    for hname in hostel_ids:
        block = hostel_blocks[hname]
        for floor in range(1, 4):
            for num in range(1, 6):
                room_no = f"{block}-{floor}{num:02d}"
                cur.execute("INSERT INTO rooms (hostel_id, room_number, capacity, occupied, status) VALUES (?, ?, ?, ?, ?)",
                            (hostel_ids[hname], room_no, 2, 0, "Available"))
                room_ids[(hname, room_no)] = cur.lastrowid

    # ---------------- Users: fixed demo accounts ----------------
    def make_user(email, password, role, name, phone=None):
        cur.execute(
            "INSERT INTO users (email, password_hash, role, name, phone) VALUES (?, ?, ?, ?, ?)",
            (email, generate_password_hash(password), role, name, phone),
        )
        return cur.lastrowid

    admin_uid = make_user("admin@campus.local", "admin123", "admin", "Admin Office", "9000000001")
    warden_uid = make_user("warden@campus.local", "warden123", "warden", "S. K. Mohapatra", "9000000002")
    mess_uid = make_user("mess@campus.local", "mess123", "mess", "R. Behera", "9000000003")
    frontdesk_uid = make_user("frontdesk@campus.local", "front123", "frontdesk", "Front Desk Staff", "9000000004")

    cur.execute("UPDATE hostels SET warden_user_id = ? WHERE name = 'Boys Hostel A'", (warden_uid,))

    # Faculty (fixed demo + a few extra so timetable/attendance has variety)
    teacher_uid = make_user("teacher@campus.local", "teacher123", "faculty", "Prof. Ramesh Chandra Naik", "9000000005")
    cur.execute("INSERT INTO faculty (user_id, employee_id, department_id, designation) VALUES (?, ?, ?, ?)",
                (teacher_uid, "TAT-FAC-001", dept_ids["Computer Science & Engineering"], "Associate Professor"))
    fac_main = cur.lastrowid

    extra_faculty = []
    used_names = {"Ramesh Chandra Naik"}
    for i in range(4):
        name = rand_name(used_names)
        email = f"faculty{i+2}@campus.local"
        uid = make_user(email, "faculty123", "faculty", f"Prof. {name}", f"90000001{i:02d}")
        cur.execute("INSERT INTO faculty (user_id, employee_id, department_id, designation) VALUES (?, ?, ?, ?)",
                    (uid, f"TAT-FAC-{i+2:03d}", dept_ids["Computer Science & Engineering"], "Assistant Professor"))
        extra_faculty.append(cur.lastrowid)

    # ---------------- Faculty-subject mapping & Timetable ----------------
    sec_3a = section_ids["CSE-3A"]
    sec_3b = section_ids["CSE-3B"]
    dbms = subject_ids["CSE501"]
    os_sub = subject_ids["CSE502"]
    cn_sub = subject_ids["CSE503"]
    se_sub = subject_ids["CSE504"]

    tt_entries = [
        (sec_3a, dbms, fac_main, "Monday", "09:00", "10:00", "301"),
        (sec_3a, os_sub, extra_faculty[0], "Monday", "10:00", "11:00", "301"),
        (sec_3a, cn_sub, extra_faculty[1], "Tuesday", "09:00", "10:00", "301"),
        (sec_3a, se_sub, extra_faculty[2], "Wednesday", "11:00", "12:00", "302"),
        (sec_3a, dbms, fac_main, "Thursday", "09:00", "10:00", "301"),
        (sec_3a, os_sub, extra_faculty[0], "Friday", "10:00", "11:00", "301"),
        (sec_3b, dbms, fac_main, "Monday", "11:00", "12:00", "303"),
        (sec_3b, cn_sub, extra_faculty[1], "Wednesday", "09:00", "10:00", "303"),
    ]
    today_weekday = datetime.now().strftime("%A")
    if today_weekday not in [e[3] for e in tt_entries]:
        tt_entries.append((sec_3a, dbms, fac_main, today_weekday, "14:00", "15:00", "301"))

    for (section_id, subject_id, faculty_id, day, start, end, room) in tt_entries:
        cur.execute(
            "INSERT INTO timetable (section_id, subject_id, faculty_id, day_of_week, start_time, end_time, room) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (section_id, subject_id, faculty_id, day, start, end, room),
        )
        cur.execute(
            "SELECT id FROM faculty_subjects WHERE faculty_id=? AND subject_id=? AND section_id=?",
            (faculty_id, subject_id, section_id),
        )
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO faculty_subjects (faculty_id, subject_id, section_id) VALUES (?, ?, ?)",
                (faculty_id, subject_id, section_id),
            )

    # ---------------- Students ----------------
    boys_a = hostel_ids["Boys Hostel A"]
    room_b101 = room_ids.get(("Boys Hostel A", "A-101"))

    # Group room ids by hostel so random assignment below never mismatches a
    # student's hostel_id against a room that actually belongs elsewhere.
    rooms_by_hostel = {}
    for (hname, room_no), rid in room_ids.items():
        rooms_by_hostel.setdefault(hname, []).append(rid)

    # The consistent demo/sample student referenced across the app
    rohit_uid = make_user("student@campus.local", "1234", "student", "Rohit Kumar", "9800000001")
    cur.execute(
        "INSERT INTO students (user_id, college_id, roll_number, branch_id, year, semester, section_id, "
        "hostel_id, room_id, guardian_name, guardian_phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (rohit_uid, "TAT-CSE-2026-001", "CSE3A01", cse_id, 3, 5, sec_3a, boys_a, room_b101,
         "Suresh Kumar", "9811111111"),
    )
    rohit_student_id = cur.lastrowid
    cur.execute("UPDATE rooms SET occupied = occupied + 1 WHERE id = ?", (room_b101,))

    # Additional students for meaningful analytics
    used_names.add("Rohit Kumar")
    all_student_ids = [rohit_student_id]
    section_pool = [sec_3a, sec_3a, sec_3a, sec_3b, sec_3b, section_ids["CSE-2A"], section_ids["ECE-3A"], section_ids["ME-2A"]]
    hostel_names = ["Boys Hostel A", "Boys Hostel B", "Girls Hostel C"]

    for i in range(24):
        name = rand_name(used_names)
        email = f"stu{i+2}@campus.local"
        uid = make_user(email, "student123", "student", name, f"98{i:08d}")
        section_id = random.choice(section_pool)
        # find branch for that section
        cur.execute("SELECT branch_id, year, semester FROM sections WHERE id = ?", (section_id,))
        b_row = cur.fetchone()
        hostel_name_choice = random.choice(hostel_names)
        hostel_choice = hostel_ids[hostel_name_choice]
        room_choice = random.choice(rooms_by_hostel[hostel_name_choice])
        college_id = f"TAT-GEN-2026-{i+2:03d}"
        cur.execute(
            "INSERT INTO students (user_id, college_id, roll_number, branch_id, year, semester, section_id, "
            "hostel_id, room_id, guardian_name, guardian_phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, college_id, f"ROLL{i+2:03d}", b_row["branch_id"], b_row["year"], b_row["semester"], section_id,
             hostel_choice, room_choice, "Guardian " + name.split()[0], f"97{i:08d}"),
        )
        sid = cur.lastrowid
        all_student_ids.append(sid)
        cur.execute("UPDATE rooms SET occupied = occupied + 1 WHERE id = ? AND occupied < capacity", (room_choice,))

    # Recompute room status based on occupancy
    cur.execute("UPDATE rooms SET status = CASE WHEN occupied >= capacity THEN 'Full' WHEN occupied = 0 THEN 'Available' ELSE 'Partially Occupied' END")

    # ---------------- Attendance (last 20 class-days for section CSE-3A subjects) ----------------
    sec3a_students = [sid for sid in all_student_ids if sid == rohit_student_id] + \
                      [sid for i, sid in enumerate(all_student_ids) if i % 3 == 0][:8]
    sec3a_students = list(dict.fromkeys(sec3a_students))  # dedupe, preserve order

    subj_for_attendance = [dbms, os_sub, cn_sub, se_sub]
    for day_offset in range(20, 0, -1):
        date = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for sid in sec3a_students:
            for subj in subj_for_attendance:
                # Rohit gets ~82% attendance; others vary 60-95%
                if sid == rohit_student_id:
                    present = random.random() < 0.82
                else:
                    present = random.random() < random.uniform(0.6, 0.95)
                status = "Present" if present else "Absent"
                try:
                    cur.execute(
                        "INSERT INTO attendance (student_id, subject_id, section_id, faculty_id, date, status) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (sid, subj, sec_3a, fac_main, date, status),
                    )
                except sqlite3.IntegrityError:
                    pass

    # ---------------- Assignments ----------------
    cur.execute(
        "INSERT INTO assignments (faculty_id, subject_id, section_id, title, description, deadline, max_marks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fac_main, dbms, sec_3a, "ER Diagram Design",
         "Design an ER diagram for a library management system and submit as PDF.",
         (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"), 100),
    )
    assignment1 = cur.lastrowid
    cur.execute(
        "INSERT INTO assignments (faculty_id, subject_id, section_id, title, description, deadline, max_marks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (extra_faculty[0], os_sub, sec_3a, "Process Scheduling Report",
         "Compare FCFS, SJF and Round Robin scheduling with examples.",
         (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"), 50),
    )
    assignment2 = cur.lastrowid

    # ---------------- Exams & Results ----------------
    cur.execute(
        "INSERT INTO exams (name, exam_type, subject_id, section_id, date, time, room, max_marks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Mid-Semester Exam", "Internal", dbms, sec_3a,
         (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"), "10:00", "Exam Hall 1", 50),
    )
    exam1 = cur.lastrowid
    cur.execute(
        "INSERT INTO exams (name, exam_type, subject_id, section_id, date, time, room, max_marks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("Internal Assessment 1", "Internal", os_sub, sec_3a,
         (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"), "10:00", "Exam Hall 2", 30),
    )
    exam2 = cur.lastrowid
    cur.execute("INSERT INTO results (exam_id, student_id, marks_obtained) VALUES (?, ?, ?)", (exam2, rohit_student_id, 24))

    # ---------------- Mess Menu ----------------
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    sample_menu = {
        "Breakfast": ["Idli & Sambar", "Poha & Tea", "Bread Omelette", "Upma", "Paratha & Curd", "Puri Sabzi", "Dosa & Chutney"],
        "Lunch": ["Rice, Dal, Mix Veg", "Rice, Sambar, Poriyal", "Roti, Paneer Curry", "Rice, Rajma", "Veg Biryani",
                  "Rice, Dal, Aloo Gobi", "Rice, Chicken Curry"],
        "Snacks": ["Samosa & Tea", "Bhel Puri", "Bread Pakora", "Vada Pav", "Chana Chaat", "Cutlet & Tea", "Sandwich"],
        "Dinner": ["Roti, Dal Fry", "Fried Rice, Manchurian", "Roti, Mix Veg", "Khichdi", "Roti, Egg Curry",
                   "Rice, Sambar", "Roti, Paneer Bhurji"],
    }
    for i, d in enumerate(days):
        for meal, items in sample_menu.items():
            cur.execute("INSERT INTO mess_menus (day_of_week, meal, items) VALUES (?, ?, ?)", (d, meal, items[i]))

    # ---------------- Mess Feedback ----------------
    for sid in random.sample(all_student_ids, 12):
        cur.execute(
            "INSERT INTO mess_feedback (student_id, meal, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (sid, random.choice(["Breakfast", "Lunch", "Snacks", "Dinner"]), random.randint(2, 5),
             random.choice(["Good taste", "Could be better", "Loved it", "Too oily", None, "Needs more variety"]),
             (datetime.now() - timedelta(days=random.randint(0, 14))).strftime("%Y-%m-%d %H:%M:%S")),
        )

    # ---------------- Requests / Complaints ----------------
    sample_requests = [
        (rohit_student_id, "Fan not working in room", "The ceiling fan in B-101 has stopped working.", "Hostel", "High", "Resolved"),
        (rohit_student_id, "WiFi very slow in hostel", "WiFi speed drops every evening after 8 PM.", "IT", "Normal", "In Progress"),
        (rohit_student_id, "Food quality complaint", "Rice was undercooked at dinner yesterday.", "Mess", "Normal", "Pending"),
    ]
    for sid, title, desc, cat, pri, status in sample_requests:
        cur.execute(
            "INSERT INTO requests (student_id, title, description, category, priority, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, title, desc, cat, pri, status, (datetime.now() - timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d %H:%M:%S")),
        )
        rid = cur.lastrowid
        if status != "Pending":
            cur.execute(
                "INSERT INTO request_updates (request_id, updated_by, old_status, new_status, note) VALUES (?, ?, ?, ?, ?)",
                (rid, warden_uid if cat == "Hostel" else admin_uid, "Pending", status, "Being handled."),
            )

    # A few recurring hostel complaints (for recurring-issue detection demo) across other students
    for i in range(5):
        sid = random.choice(all_student_ids)
        cur.execute(
            "INSERT INTO requests (student_id, title, description, category, priority, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, "Water leakage in bathroom", "Recurring water leakage issue.", "Hostel", "Normal", "Pending",
             (datetime.now() - timedelta(days=random.randint(1, 25))).strftime("%Y-%m-%d %H:%M:%S")),
        )

    # ---------------- Leave Requests ----------------
    cur.execute(
        "INSERT INTO leave_requests (student_id, leave_type, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
        (rohit_student_id, "Medical Leave", (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
         (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"), "Fever and needs rest.", "Pending"),
    )

    # ---------------- Notices ----------------
    cur.execute(
        "INSERT INTO notices (title, body, notice_type, target_audience, created_by) VALUES (?, ?, ?, ?, ?)",
        ("Welcome to Semester 5", "Classes begin Monday. Please check your timetable.", "Academic", "Everyone", admin_uid),
    )
    cur.execute(
        "INSERT INTO notices (title, body, notice_type, target_audience, target_value, created_by) VALUES (?, ?, ?, ?, ?, ?)",
        ("Hostel Water Supply Maintenance", "Water supply will be interrupted 10 AM - 2 PM for maintenance.",
         "Hostel", "Hostel", "Boys Hostel A", warden_uid),
    )

    # ---------------- Entry Logs ----------------
    for day_offset in range(3, 0, -1):
        d = datetime.now() - timedelta(days=day_offset)
        cur.execute(
            "INSERT INTO entry_logs (student_id, college_id, gate, entry_type, timestamp, operator_id) VALUES (?, ?, ?, ?, ?, ?)",
            (rohit_student_id, "TAT-CSE-2026-001", "Main Gate", "IN", d.strftime("%Y-%m-%d") + " 08:32:00", frontdesk_uid),
        )
        cur.execute(
            "INSERT INTO entry_logs (student_id, college_id, gate, entry_type, timestamp, operator_id) VALUES (?, ?, ?, ?, ?, ?)",
            (rohit_student_id, "TAT-CSE-2026-001", "Main Gate", "OUT", d.strftime("%Y-%m-%d") + " 17:45:00", frontdesk_uid),
        )

    conn.commit()
    conn.close()
    print("CampusOne database initialized and seeded successfully at:", DB_PATH)


if __name__ == "__main__":
    main()
