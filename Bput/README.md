# CampusOne
### "Campus Life, Debugged."

CampusOne is a complete, working college management and campus-life platform
built for **Trident Academy of Technology**. It runs entirely on your own
Windows PC from one extracted folder — no cloud account, no paid services,
and no internet connection required for its core features.

---

## 1. Features

**Six role-based portals**, each showing only what that role needs:

| Role | Highlights |
|---|---|
| **Student** | Dashboard, subject-wise attendance %, assignments (submit + grades), exam schedule & results, requests/complaints, leave applications, hostel info, mess menu + feedback, notices, notifications, entry/exit history, AI campus assistant |
| **Faculty** | Today's classes, mark attendance (present/absent, saved per date), create & grade assignments, view timetable |
| **Admin** | Command center with live analytics (requests by category/status/priority, attendance trends, hostel occupancy, recurring-issue detection), full request lifecycle management with SLA ageing, user management, notice broadcast with targeting, exam scheduling & results entry, timetable management, academic management (departments/branches/subjects/sections, auto-synced faculty-subject mapping), hostel/room creation & student allocation, audit log |
| **Warden** | Hostel occupancy dashboard, complaint handling, leave approvals, room overview |
| **Mess Manager** | Weekly menu editor, feedback & ratings dashboard, complaint handling |
| **Front Desk** | Record entry/exit by College ID, student lookup, assisted request creation for students with low connectivity |

**Also included:**
- Real SQLite database with 24 linked tables (attendance, requests, hostel
  allocations, leave, exams, results, notifications, audit logs, etc.) — every
  button and form writes real data, nothing is mocked.
- **My Account** page for every role — edit name/phone, upload a profile
  photo (shown as an avatar in the top bar), and change password with
  current-password verification.
- Live Chart.js visualizations on the Admin Command Center, Attendance
  Analytics, Warden, and Mess dashboards (requests by category/status/
  priority, hostel occupancy, attendance trends, meal ratings) — skipped
  entirely in Lite Mode to save bandwidth, with the underlying data still
  shown as plain lists either way.
- Request/complaint system with priority, SLA ageing & overdue flags, status
  pipeline (Pending → Assigned → In Progress → Resolved/Rejected/Reopened),
  and full audit trail of every change.
- In-app notification center (always works) with optional email fallback and
  a WhatsApp status abstraction, both of which degrade gracefully with no
  crashes if unconfigured.
- Rule-based AI Campus Assistant that answers attendance/exam/mess/complaint
  questions directly from the database — no external AI key required. Ready
  to be pointed at Gemini or a local Ollama model later via `.env`.
- Recurring-issue detection (e.g. "8 hostel water-leakage complaints in 30
  days") on the admin dashboard.
- Basic PWA support (installable, offline page caching, offline request
  queue that syncs when connection returns) and a **Lite Mode** toggle for
  patchy campus WiFi.
- CSRF protection, hashed passwords, file-type/size validated uploads,
  role-based route protection, and a full audit log of sensitive actions.

---

## 2. Technology Stack

- **Backend:** Python 3 + Flask
- **Database:** SQLite (zero setup — one file, no server)
- **Frontend:** HTML5, CSS3, vanilla JavaScript (no framework)
- **PWA:** manifest.json + service worker

---

## 3. Windows Setup (Easy Mode)

**Requirements:** Python 3.10+ installed ([python.org](https://www.python.org/downloads/)),
with **"Add Python to PATH"** checked during install.

1. Extract the `CampusOne` folder anywhere (e.g. `C:\CampusOne`).
2. Double-click **`setup.bat`**. This will:
   - Check Python is installed
   - Create a virtual environment (`venv`)
   - Install dependencies
   - Create a `.env` file from the template
   - Initialize and seed the database with demo data
3. Double-click **`run.bat`** to start the server.
4. Open your browser to **http://127.0.0.1:5000**

Other devices on the same WiFi/campus network can also reach it at
`http://<your-PC's-LAN-IP>:5000` (the terminal will print this address).

### Manual setup (if you prefer the command line)
```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
venv\Scripts\python init_db.py
venv\Scripts\python app.py
```

---

## 3b. Running in VS Code / on macOS / Linux

CampusOne is a standard Flask project, so it opens and runs in VS Code (or
any editor) exactly as-is — the folder needs no special configuration.

- **On Windows in VS Code:** open the `CampusOne` folder, open the built-in
  terminal (`` Ctrl+` ``), and run `setup.bat` then `run.bat` — they work the
  same way there as double-clicking them.
- **On macOS / Linux (in VS Code's terminal or any shell):** use the `.sh`
  equivalents instead, since `.bat` files are Windows-only:
  ```bash
  chmod +x setup.sh run.sh   # first time only
  ./setup.sh
  ./run.sh
  ```
- You can also just press **Run/Debug** on `app.py` directly in VS Code once
  `setup.sh`/`setup.bat` has created the virtual environment and database —
  make sure VS Code's selected Python interpreter is the one inside `venv/`
  (bottom-right of the VS Code window, or `Python: Select Interpreter` from
  the command palette).

---

## 4. Demo Login Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@campus.local | admin123 |
| Student | student@campus.local | 1234 |
| Faculty | teacher@campus.local | teacher123 |
| Warden | warden@campus.local | warden123 |
| Mess Manager | mess@campus.local | mess123 |
| Front Desk | frontdesk@campus.local | front123 |

The seeded demo student is **Rohit Kumar**, College ID `TAT-CSE-2026-001`,
CSE branch, Year 3 / Semester 5, Boys Hostel A, Room A-101. Twenty-four
additional students, five faculty, and several weeks of attendance/requests
history are also seeded so the analytics views have realistic data.

---

## 5. Database

A single SQLite file at `database/campusone.db`, created and seeded by
`init_db.py`. Re-running `init_db.py` **wipes and rebuilds** the database
from scratch with fresh demo data — use it to reset the demo at any time:

```bat
venv\Scripts\python init_db.py
```

Schema (`schema.sql`) covers: users, students, faculty, departments,
branches, sections, subjects, timetable, attendance, assignments &
submissions, exams & results, hostels, rooms, hostel allocations, mess menus
& feedback, requests & request updates, leave requests, entry logs, notices
& receipts, notifications, and audit logs — with foreign keys and indexes.

---

## 6. Environment Variables

Copy `.env.example` to `.env` and fill in values **only if you want the
optional integrations below**. CampusOne works completely normally with all
of these left blank.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing key. Change for anything beyond local demo use. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_FROM` | SMTP email notifications for student alerts. Configure all required values in `.env`; Gmail users should use an App Password. If blank or invalid, in-app notifications still work but no email is sent. |
| `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_ID` | Optional WhatsApp status abstraction (no paid API required for core app). If blank, status shows "Not configured". |
| `GEMINI_API_KEY` / `OLLAMA_HOST` | Optional — routes the Campus Assistant to a real LLM. Without these, a built-in rule-based engine answers attendance/exam/mess/complaint questions directly from the database. |

---

## 7. Project Structure

```
CampusOne/
├── app.py                  # Flask app factory + entry point
├── config.py                # Configuration (reads .env)
├── init_db.py                # Schema creation + demo data seeding
├── schema.sql                # Database schema (24 tables)
├── requirements.txt
├── .env.example
├── setup.bat / run.bat       # Windows setup & run scripts
├── blueprints/                # One Flask blueprint per role + shared routes
│   ├── auth.py, student.py, faculty.py, admin.py,
│   ├── warden.py, mess.py, frontdesk.py, api.py, common.py
├── utils/                     # DB helper, auth decorators, audit log,
│   │                           notifications, SLA calc, upload validation,
│   │                           AI assistant
├── templates/                 # Jinja2 templates, one folder per role
│   ├── base.html, login.html, error.html
│   ├── student/ faculty/ admin/ warden/ mess/ frontdesk/
├── static/
│   ├── css/style.css          # Design system
│   ├── js/main.js             # Sidebar, offline queue, SW registration
│   ├── service-worker.js
│   └── icons/
├── database/campusone.db      # Created by init_db.py (not in the zip)
└── uploads/                   # Request photos/videos, assignments, leave docs
```

---

## 8. Health Check

`GET /api/health` → `{"status": "ok", "app": "CampusOne", "database": "ok"}`

---

## 9. Demo Workflow Suggestion

1. Log in as **Student** → submit a hostel complaint with a photo, apply for
   leave, check attendance, ask the Campus Assistant "What is my attendance?"
2. Log in as **Faculty** → mark today's attendance for a class, create an
   assignment.
3. Log in as **Warden** → resolve the hostel complaint, approve the leave
   request.
4. Log in as **Admin** → open the Command Center to see the complaint show
   up in analytics, check the SLA/overdue view, check the audit log.
5. Log in as **Front Desk** → look up the student by College ID and record
   an entry/exit.
6. Log in as **Mess Manager** → update the weekly menu, review feedback.

---

## 10. Troubleshooting

- **"Python was not found"** — reinstall Python and check "Add Python to
  PATH", then re-run `setup.bat`.
- **Port 5000 already in use** — close whatever else is using it, or edit
  the port number at the bottom of `app.py`.
- **Database looks empty / out of date** — re-run
  `venv\Scripts\python init_db.py` to reset it.
- **Uploaded files not showing** — check the `uploads/` folder exists and
  the app has permission to write to it.
- **Email/WhatsApp/AI "not configured" messages** — expected unless you've
  filled in the relevant `.env` variables; every other feature still works.

---

## 11. Known Limitations

- The AI Campus Assistant's rule-based engine understands attendance, exam,
  mess-menu, and request/complaint questions specifically; it is not a
  general-purpose chatbot unless wired to a real LLM via `.env`.
- WhatsApp integration is a status-only abstraction (Not configured / Queued
  / Sent / Failed) — no default provider is wired in.
- The offline request queue relies on browser `localStorage` and syncs on
  reconnect; it is a best-effort convenience, not a guaranteed sync engine.
- This uses Flask's built-in development server, which is intentional for a
  local/demo deployment — for real production use behind a public network, run
  it behind a proper WSGI server (e.g. waitress) instead.
- Creating a user in Admin → Users only creates the login account; a full
  student/faculty profile (branch, section, hostel, etc.) is set up via the
  database/seed process, not yet through a dedicated admin UI.
