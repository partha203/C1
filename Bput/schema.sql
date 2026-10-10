PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','faculty','admin','warden','mess','frontdesk')),
    name TEXT NOT NULL,
    phone TEXT,
    photo TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    department_id INTEGER REFERENCES departments(id)
);

CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id INTEGER REFERENCES branches(id),
    year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    branch_id INTEGER REFERENCES branches(id),
    semester INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS faculty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id),
    employee_id TEXT UNIQUE,
    department_id INTEGER REFERENCES departments(id),
    designation TEXT
);

CREATE TABLE IF NOT EXISTS faculty_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER REFERENCES faculty(id),
    subject_id INTEGER REFERENCES subjects(id),
    section_id INTEGER REFERENCES sections(id)
);

CREATE TABLE IF NOT EXISTS hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    block TEXT,
    warden_user_id INTEGER REFERENCES users(id),
    capacity INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id INTEGER REFERENCES hostels(id),
    room_number TEXT NOT NULL,
    capacity INTEGER DEFAULT 2,
    occupied INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Available'
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE REFERENCES users(id),
    college_id TEXT UNIQUE NOT NULL,
    roll_number TEXT,
    branch_id INTEGER REFERENCES branches(id),
    year INTEGER,
    semester INTEGER,
    section_id INTEGER REFERENCES sections(id),
    hostel_id INTEGER REFERENCES hostels(id),
    room_id INTEGER REFERENCES rooms(id),
    guardian_name TEXT,
    guardian_phone TEXT
);

CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER REFERENCES sections(id),
    subject_id INTEGER REFERENCES subjects(id),
    faculty_id INTEGER REFERENCES faculty(id),
    day_of_week TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    room TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    subject_id INTEGER REFERENCES subjects(id),
    section_id INTEGER REFERENCES sections(id),
    faculty_id INTEGER REFERENCES faculty(id),
    date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Present','Absent')),
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, subject_id, date)
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER REFERENCES faculty(id),
    subject_id INTEGER REFERENCES subjects(id),
    section_id INTEGER REFERENCES sections(id),
    title TEXT NOT NULL,
    description TEXT,
    deadline TEXT,
    attachment TEXT,
    max_marks INTEGER DEFAULT 100,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assignment_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER REFERENCES assignments(id),
    student_id INTEGER REFERENCES students(id),
    file_path TEXT,
    submitted_at TEXT DEFAULT (datetime('now')),
    marks_obtained INTEGER,
    feedback TEXT,
    UNIQUE(assignment_id, student_id)
);

CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    exam_type TEXT,
    subject_id INTEGER REFERENCES subjects(id),
    section_id INTEGER REFERENCES sections(id),
    date TEXT,
    time TEXT,
    room TEXT,
    max_marks INTEGER DEFAULT 100,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER REFERENCES exams(id),
    student_id INTEGER REFERENCES students(id),
    marks_obtained REAL,
    UNIQUE(exam_id, student_id)
);

CREATE TABLE IF NOT EXISTS hostel_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    room_id INTEGER REFERENCES rooms(id),
    allocated_at TEXT DEFAULT (datetime('now')),
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS mess_menus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day_of_week TEXT NOT NULL,
    meal TEXT NOT NULL CHECK(meal IN ('Breakfast','Lunch','Snacks','Dinner')),
    items TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(day_of_week, meal)
);

CREATE TABLE IF NOT EXISTS mess_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    meal TEXT,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'Normal' CHECK(priority IN ('Low','Normal','High','Urgent')),
    photo TEXT,
    video TEXT,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending','Assigned','In Progress','Resolved','Rejected','Reopened')),
    assigned_to TEXT,
    assigned_at TEXT,
    resolution_note TEXT,
    created_by_role TEXT DEFAULT 'student',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS request_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER REFERENCES requests(id),
    updated_by INTEGER REFERENCES users(id),
    old_status TEXT,
    new_status TEXT,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    document TEXT,
    status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','Approved','Rejected')),
    reviewed_by INTEGER REFERENCES users(id),
    reviewed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entry_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER REFERENCES students(id),
    college_id TEXT,
    gate TEXT DEFAULT 'Main Gate',
    entry_type TEXT CHECK(entry_type IN ('IN','OUT')),
    timestamp TEXT DEFAULT (datetime('now')),
    operator_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT,
    notice_type TEXT DEFAULT 'General',
    target_audience TEXT DEFAULT 'Everyone',
    target_value TEXT,
    requires_ack INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notice_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id INTEGER REFERENCES notices(id),
    student_id INTEGER REFERENCES students(id),
    read_at TEXT,
    acknowledged_at TEXT,
    UNIQUE(notice_id, student_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    ntype TEXT,
    title TEXT,
    body TEXT,
    link TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity TEXT,
    entity_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_student ON requests(student_id);
CREATE INDEX IF NOT EXISTS idx_entry_student ON entry_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
