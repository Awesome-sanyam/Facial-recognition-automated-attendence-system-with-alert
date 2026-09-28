# 🎓 Facial Recognition Automated Attendance System with RPA Alert Bot

> **A complete university attendance management platform** — students are marked present by their face, faculty manage records through a web portal, and an RPA bot automatically emails/SMS-alerts parents of low-attendance students.

---

## 📑 Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Database Models](#5-database-models)
6. [All URL Routes](#6-all-url-routes)
7. [Component Deep-Dives](#7-component-deep-dives)
8. [Step-by-Step: How Everything Works Together](#8-step-by-step-how-everything-works-together)
9. [Environment Variables](#9-environment-variables)
10. [Complete Setup Guide (Fresh Machine)](#10-complete-setup-guide-fresh-machine)
11. [How to Run the Project](#11-how-to-run-the-project)
12. [How to Run the RPA Bot](#12-how-to-run-the-rpa-bot)
13. [Gmail App Password Setup](#13-gmail-app-password-setup)
14. [Twilio SMS Setup (Optional)](#14-twilio-sms-setup-optional)
15. [Common Errors and Fixes](#15-common-errors-and-fixes)

---

## 1. Project Overview

This system solves three real-world problems in university attendance management:

| Problem | Solution in This Project |
|---|---|
| Manual roll-calls are slow and can be faked | **Facial Recognition** marks attendance automatically via webcam |
| Faculty waste time emailing parents manually | **RPA Bot** auto-sends email + SMS alerts for low attendance |
| No central dashboard for student/leave management | **Django Web Portal** for faculty with full CRUD and analytics |

### Two ways to mark attendance:
1. **Live Scanner** (`scanner.py`) — runs on a classroom PC with a webcam, continuously scans faces and marks attendance in the DB in real-time
2. **Web Face Login** (`face_login_api`) — students open the browser, click "Login with Face", their webcam captures a frame, the server recognises them and marks attendance

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PROJECT ROOT                                │
│                                                                     │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │ face_recognition│   │    web_app/       │   │   rpa_bot/      │  │
│  │                 │   │  (Django 6)       │   │  (Robot FW)     │  │
│  │  scanner.py     │   │                  │   │                 │  │
│  │  (classroom)    │   │  ┌────────────┐  │   │  tasks.robot    │  │
│  │                 │◄──┼──│  SQLite DB │  │   │  EmailLibrary   │  │
│  │  face_login.py  │   │  │ db.sqlite3 │  │   │  SmsLibrary     │  │
│  │  (web API)      │──►┼──└────────────┘  │   │                 │  │
│  │                 │   │                  │   │  Selenium /     │  │
│  │  known_faces/   │   │  Faculty Portal  │   │  Chrome         │  │
│  │  (photo store)  │   │  Student Portal  │   │                 │  │
│  └─────────────────┘   └──────────────────┘   └────────┬────────┘  │
│                                                         │           │
│                              ┌──────────────────────────┘           │
│                              ▼                                      │
│                    ┌─────────────────┐                              │
│                    │  External APIs  │                              │
│                    │  Gmail SMTP     │                              │
│                    │  Twilio SMS     │                              │
│                    └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. Webcam frame → `face_login.py` → compare against `known_faces/` → match → `AttendanceRecord` created in DB
2. Faculty logs into web portal → views student roster with attendance % → clicks "Run Alert Bot"
3. RPA bot (`tasks.robot`) opens Chrome → logs into faculty portal → scrapes student table → sends Email/SMS via Gmail + Twilio for every student below threshold

---

## 3. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| **Web Framework** | Django | 6.0.7 |
| **Database** | SQLite (default) / PostgreSQL (optional) | — |
| **Security & Encryption** | `cryptography` (AES-128 Fernet) | 50.0.1 |
| **Face Recognition** | `face_recognition` library (dlib-based) | 1.3.0 |
| **Computer Vision** | OpenCV (`opencv-python`) | 5.0.0 |
| **RPA Automation** | Robot Framework | 7.4.2 |
| **Browser Automation** | SeleniumLibrary + ChromeDriver | 6.9.0 |
| **Email** | smtplib / Gmail SMTP | built-in |
| **SMS** | Twilio REST API | 9.10.9 |
| **Environment** | python-dotenv | 1.2.2 |
| **Language** | Python | 3.10+ |

---

## 4. Project Folder Structure

```
RPA Project/
│
├── .env                        # Your actual secrets (NEVER commit this)
├── .env.example                # Template — copy to .env and fill in
├── .gitignore                  # Excludes .env, .venv, __pycache__, etc.
├── requirements.txt            # All Python dependencies (pip install -r)
├── run_rpa_bot.sh              # One-click zero-mutation script to run the RPA bot
├── About.md                    # THIS FILE — full project documentation
├── Report.md                   # Full architectural audit and gap analysis
│
├── face_recognition/
│   ├── known_faces/            # Image store (synced with DB vector embeddings)
│   │   └── ENR2024001.jpg      # e.g. ENR2024001.jpg for student with that enrollment number
│   ├── face_login.py           # API: DB-backed 128-d vector matching + in-memory cache
│   └── scanner.py              # Standalone: real-time webcam scanner (frame-skipping + DB cache)
│
├── web_app/
│   ├── manage.py               # Django management entry point
│   ├── db.sqlite3              # SQLite database file (auto-created on first migrate)
│   │
│   ├── attendance_system/      # Django PROJECT config (settings, root URLs)
│   │   ├── settings.py         # All Django settings (DB, timezone=IST, logging, etc.)
│   │   ├── urls.py             # Root URL dispatcher — includes core.urls
│   │   └── wsgi.py / asgi.py   # WSGI/ASGI entry points
│   │
│   └── core/                   # Django APP — all business logic lives here
│       ├── crypto.py           # AES-128 Fernet symmetric encryption for sensitive credentials
│       ├── models.py           # DB models: FacultyProfile, Student, AttendanceRecord, etc.
│       ├── views.py            # All view functions with alert engine and leave workflows
│       ├── urls.py             # URL patterns for all routes
│       ├── tests.py            # Comprehensive test suite (32 unit/integration tests)
│       ├── admin.py            # Django admin customisation
│       ├── management/         # Custom Django management commands
│       │   └── commands/
│       │       ├── reconcile_attendance.py  # Daily cron/CLI absent attendance reconciliation
│       │       └── sync_face_encodings.py   # Bulk extract & sync 128-d face vectors into DB
│       ├── templates/core/     # HTML templates (9 pages)
│       │   ├── home.html              # Landing page
│       │   ├── login.html             # Student login + face recognition UI + PIN entry
│       │   ├── dashboard.html         # Student's personal dashboard
│       │   ├── apply_leave.html       # Student leave application form
│       │   ├── faculty_login.html     # Faculty login page
│       │   ├── faculty_register.html  # Faculty registration form
│       │   ├── faculty_pending.html   # "Awaiting approval" screen
│       │   ├── faculty_dashboard.html # Main faculty control panel (4 tabs + direct photo upload)
│       │   └── _theme_css.html        # Shared CSS variables/theme
│       └── migrations/         # Auto-generated DB migration files
│
└── rpa_bot/
    ├── tasks.robot             # Main Robot Framework script (the RPA bot)
    ├── EmailLibrary.py         # Custom email keyword library (smtplib wrapper)
    ├── SmsLibrary.py           # Custom SMS keyword library (Twilio wrapper)
    ├── resources/              # Shared Robot Framework resources (if any)
    ├── log.html                # Last run log (auto-generated by Robot FW)
    ├── output.xml              # Last run output XML
    └── report.html             # Last run summary report
```

---

## 5. Database Models

The app uses **5 Django models** defined in `web_app/core/models.py`:

### FacultyProfile
Extends Django's built-in `User` with faculty-specific fields.

| Field | Type | Description |
|---|---|---|
| `user` | OneToOneField → User | Linked Django auth user |
| `department` | CharField | e.g., "Computer Science" |
| `phone` | CharField | Contact number |
| `is_approved` | BooleanField | False until a superuser approves |
| `registered_at` | DateTimeField | Auto-set on creation |

> New faculty accounts start with `is_active=False` AND `is_approved=False`. A Django superuser must approve them in the admin panel before they can log in.

---

### AlertConfiguration
One-per-faculty record storing all RPA/alert settings. Sensitive credentials (`gmail_app_password`, `twilio_account_sid`, `twilio_auth_token`) are symmetrically encrypted using Fernet (AES-128-CBC + HMAC-SHA256) before saving to the database.

| Field | Type | Description |
|---|---|---|
| `faculty` | OneToOneField → FacultyProfile | Owner |
| `gmail_address` | EmailField | Gmail account to send from |
| `gmail_app_password` | CharField (Encrypted) | Google App Password (stored encrypted via AES-128 Fernet) |
| `alert_threshold` | IntegerField | Default 75 — students below this % get alerted |
| `email_alerts_enabled` | BooleanField | Toggle email alerts |
| `alert_email_subject` | CharField | Customisable email subject |
| `alert_email_body` | TextField | Template with {student_name}, {attendance_percentage}, {threshold} |
| `twilio_account_sid` | CharField (Encrypted) | Twilio Account SID (stored encrypted via AES-128 Fernet) |
| `twilio_auth_token` | CharField (Encrypted) | Twilio Auth Token (stored encrypted via AES-128 Fernet) |
| `twilio_from_number` | CharField | Twilio phone number (E.164 format) |
| `sms_alerts_enabled` | BooleanField | Toggle SMS alerts |
| `last_run_at` | DateTimeField | Timestamp of last alert run |

---

### Student
Every student registered in the system.

| Field | Type | Description |
|---|---|---|
| `name` | CharField | Full name |
| `enrollment_number` | CharField (unique) | e.g., ENR2024001 — unique student identifier |
| `pin_code` | CharField (optional) | 6-digit numeric security PIN for enrollment login |
| `face_encoding` | TextField (JSON) | 128-dimensional dlib face embedding vector stored directly in DB |
| `email` | EmailField | Student's email (optional) |
| `parent_email` | EmailField | Alert emails go here |
| `parent_phone` | CharField | Alert SMS goes here |
| `department` | CharField | Department name |
| `year` | IntegerField | 1st/2nd/3rd/4th year |
| `added_by` | FK → FacultyProfile | Which faculty added this student |

**Computed properties (Python, not DB columns):**
- `attendance_percentage` — `present / (total - excused) * 100` (Excused leaves do not decrease attendance)
- `needs_alert` — True if attendance_percentage < alert threshold (default 75%)

---

### AttendanceRecord
One record per student per day.

| Field | Type | Description |
|---|---|---|
| `student` | FK → Student | Which student |
| `date` | DateField (default=today) | Date of attendance (IST timezone) |
| `time` | TimeField (auto) | Time of marking |
| `status` | CharField | "Present", "Absent", or "Excused" |

> Unique constraint: `(student, date)` — a student can only have one record per day. Approved leaves automatically set or convert the day's record to `Excused`.

---

### LeaveApplication
Students can submit leave requests, faculty can approve/reject.

| Field | Type | Description |
|---|---|---|
| `student` | FK → Student | Applicant |
| `date_requested` | DateField | Date the leave is for |
| `reason` | TextField | Written reason |
| `status` | CharField | Pending / Approved / Rejected |
| `reviewed_by` | FK → FacultyProfile | Who reviewed it |
| `reviewed_at` | DateTimeField | When it was reviewed |

---

## 6. All URL Routes

Defined in `web_app/core/urls.py`:

| URL | View | Who accesses it |
|---|---|---|
| `/` | `home` | Everyone — landing page |
| `/student/login/` | `student_login` | Students — enrollment number login |
| `/student/logout/` | `student_logout` | Students |
| `/student/face-login/` | `face_login_api` | Called by browser JS with base64 webcam frame |
| `/dashboard/<enrollment>/` | `dashboard` | Logged-in student — attendance and leave history |
| `/apply-leave/<enrollment>/` | `apply_leave` | Student — submit leave request |
| `/faculty/register/` | `faculty_register` | New faculty — registration form |
| `/faculty/pending/` | `faculty_pending` | Faculty — "awaiting approval" screen |
| `/faculty/login/` | `faculty_login` | Faculty — log in |
| `/faculty/logout/` | `faculty_logout` | Faculty — log out |
| `/faculty/dashboard/` | `faculty_dashboard` | Faculty — main control panel |
| `/faculty/student/add/` | `add_student` | Faculty — add a new student |
| `/faculty/student/delete/<id>/` | `delete_student` | Faculty — delete a student |
| `/faculty/leave/<id>/<action>/` | `manage_leave` | Faculty — approve or reject leave |
| `/faculty/alerts/save/` | `save_alert_config` | Faculty — save Gmail/Twilio/threshold config |
| `/faculty/alerts/run/` | `run_alert_bot` | Faculty — trigger alerts via Python (smtplib) |

---

## 7. Component Deep-Dives

### A. Face Recognition — face_recognition/

#### known_faces/ — The Photo Database
This folder is the "identity database". For each student, store one clear face photo named exactly as their enrollment number:

```
known_faces/
├── ENR2024001.jpg    ← Student with enrollment ENR2024001
├── ENR2024002.jpg
└── ENR2024003.png    ← .png is also accepted
```

The system extracts 128-dimensional face encodings from these images at startup.

---

#### face_login.py — Web-Based Face Login API

Called by the Django view `face_login_api` when a student clicks "Login with Face" in the browser.

**Algorithm (step by step):**
1. Receive a base64-encoded JPEG from the browser (captured from webcam via JavaScript)
2. Decode it into a NumPy array using OpenCV
3. Convert BGR → RGB (OpenCV uses BGR, `face_recognition` uses RGB)
4. Locate faces in the frame with `face_recognition.face_locations()`
5. Extract 128-d encoding with `face_recognition.face_encodings()`
6. Calculate Euclidean distance to all known face encodings
7. If best match distance < 0.6 (configurable tolerance), return the enrollment number
8. Django view then creates an `AttendanceRecord` and logs the student in

**Caching:** Face encodings are loaded once on first call and cached in memory. When a new student is added via the faculty dashboard, `invalidate_cache()` is called automatically so the new student can immediately use face login without a server restart.

---

#### scanner.py — Classroom Attendance Scanner

A standalone Python script (not part of Django) that opens the machine's webcam and continuously marks attendance.

**How it works:**
1. Loads all photos from `known_faces/` into memory at startup
2. Opens webcam (`cv2.VideoCapture(0)`)
3. For every frame:
   - Resize to 50% for faster processing
   - Detect all faces with `face_recognition.face_locations()`
   - For each face, compute distance to known encodings
   - If match found (distance < 0.6): look up student in Django DB, create AttendanceRecord (prevents duplicates on same day)
   - Display confidence % and student name on the video feed
4. Draw green box (known) or red box (unknown) around each face
5. Press `q` to quit

> `scanner.py` connects directly to the Django SQLite database using Django's ORM (it runs `django.setup()` at the top).

---

### B. Django Web App — web_app/

#### Student Portal Flow
```
Student → /student/login/ → enter enrollment number → /dashboard/<enrollment>/
                OR
Student → click "Login with Face" → webcam opens →
          browser captures frame → POST /student/face-login/ (base64 image) →
          Django runs face_recognition → creates AttendanceRecord →
          redirects to /dashboard/<enrollment>/
```

The Student Dashboard shows:
- Current attendance percentage with a progress bar
- Last 10 attendance records (date + Present/Absent)
- Last 5 leave applications and their status
- "Apply for Leave" button

---

#### Faculty Portal Flow
```
Faculty → /faculty/register/ → pending approval →
Superuser approves in Django Admin (sets is_approved=True, is_active=True) →
Faculty → /faculty/login/ → /faculty/dashboard/
```

The Faculty Dashboard has 4 tabs:

| Tab | What it shows |
|---|---|
| Students | Full student roster with attendance %, low-attendance count, add/delete student |
| Attendance | Recent 60 attendance records across all students |
| Leaves | Pending leave requests to approve/reject + full leave history |
| Alert Config | Gmail/Twilio setup form + "Run Alert Bot" button |

---

#### Alert System — Two Ways to Send Alerts

**Method 1 — Python Button (instant, in-browser):**
- Faculty clicks "Send Alerts Now" button on the Alert Config tab
- `run_alert_bot` view is called (POST to `/faculty/alerts/run/`)
- Django directly uses `smtplib` + `twilio` to send emails/SMS
- Works even without Robot Framework installed
- Shows a summary toast message when done

**Method 2 — RPA Bot (visible, automated):**
- Faculty (or developer) runs `bash run_rpa_bot.sh` from terminal
- Robot Framework opens Chrome, logs into the portal, scrapes the student table, and sends alerts
- Every step is visible with highlighted elements and slow speed
- Full HTML report generated at `/tmp/rpa_results/report.html`

---

### C. RPA Bot — rpa_bot/

#### tasks.robot — The Main Script

The Robot Framework script that automates the browser to perform the alert workflow.

**The 6 Steps it executes:**

| Step | Keyword | What happens |
|---|---|---|
| 1 | `Open Faculty Web Portal` | Opens Chrome, navigates to http://127.0.0.1:8000/faculty/login/, maximises window |
| 2 | `Login To Faculty Portal` | Highlights username field → types username → highlights password → types it → highlights submit button → clicks it → waits for dashboard |
| 3 | `Navigate To Student Attendance Roster` | Goes to ?tab=students on the dashboard |
| 4 | `Authorize Email Server` | Calls EmailLibrary.authorize() → opens SMTP connection to Gmail |
| 5 | `Authorize SMS Server` | Calls SmsLibrary.authorize_sms() → initialises Twilio client |
| 6 | `Audit And Alert Low Attendance Students` | Loops over every student row in the table, reads data-* attributes, sends email + optional SMS for students below threshold |

**Speed Control:**
- `Set Selenium Speed    1.0s` — every action has a 1-second gap
- `Highlight Element` — orange border drawn on each element before interaction
- Console banners printed at each step
- Easily tunable: change `1.0s` to `0.5s` for faster, `2.0s` for slower

---

#### EmailLibrary.py — Custom Email Library

A lightweight wrapper around Python's `smtplib`. Robot Framework keywords provided:

| Keyword | What it does |
|---|---|
| `Authorize` | Opens SMTP connection, runs STARTTLS, logs in with Gmail credentials |
| `Send Message` | Sends an EmailMessage via the open SMTP connection |
| `Close Connection` | Quits the SMTP connection gracefully |

Uses a persistent SMTP connection (opened once, reused for all students) to avoid Gmail rate limits.

---

#### SmsLibrary.py — Custom SMS Library

Wrapper around the Twilio REST API.

| Keyword | What it does |
|---|---|
| `Authorize SMS` | Initialises the `twilio.rest.Client` with SID + Auth Token |
| `Send Sms` | Sends an SMS to the given phone number via Twilio |

Auto-prefixes +91 for Indian numbers that don't start with +. Uses TRY/EXCEPT to gracefully handle Twilio trial account "unverified number" errors.

---

#### run_rpa_bot.sh — One-Click Shell Script

The shell script that:
1. Activates the virtual environment if not already active
2. Injects credentials from the DB into `tasks.robot` (rewrites the GMAIL_USER, GMAIL_PASS, Twilio variables via Python regex)
3. Runs `robot tasks.robot` — the actual RPA execution
4. Resets credentials in `tasks.robot` back to placeholders (security — safe to commit)
5. Opens the HTML report automatically in your browser

---

## 8. Step-by-Step: How Everything Works Together

```
1. SETUP
   └── Faculty registers → Superuser approves → Faculty logs in

2. ADD STUDENTS
   └── Faculty Dashboard → Students tab → "Add Student" form
       → Enter name, enrollment number, parent email/phone
       → Student added to DB

3. ADD FACE PHOTOS
   └── Put a clear photo of each student in face_recognition/known_faces/
       Named as their enrollment number (e.g., ENR2024001.jpg)

4. MARK ATTENDANCE (choose one)

   Option A — Classroom Scanner:
   └── Terminal: python face_recognition/scanner.py
       → Webcam opens → Scans faces → Marks attendance in DB automatically

   Option B — Student Web Login:
   └── Student opens http://127.0.0.1:8000/student/login/
       → Clicks "Login with Face"
       → Webcam permission requested
       → Frame captured → sent to server → face matched → attendance marked
       → Redirected to their dashboard

5. STUDENT APPLIES FOR LEAVE (optional)
   └── Student Dashboard → "Apply for Leave" → fills date + reason
       → Faculty sees it in "Leaves" tab → Approves or Rejects

6. CONFIGURE ALERTS
   └── Faculty Dashboard → Alert Config tab
       → Enter Gmail address + App Password
       → Set threshold (default 75%)
       → Optionally configure Twilio for SMS
       → Click "Save Configuration"

7. SEND ALERTS

   Option A — Instant (Python button):
   └── Click "Send Alerts Now" in the dashboard
       → Django directly emails all low-attendance parents

   Option B — RPA Bot (visible browser automation):
   └── Terminal: bash run_rpa_bot.sh
       → Chrome opens with orange element highlights
       → Bot logs in, navigates, reads table, sends emails/SMS
       → HTML report opens in browser when done
```

---

## 9. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | insecure dev fallback | Django secret key — generate a real one for production |
| `DEBUG` | `True` | Set to `False` in production |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated list of allowed hostnames |
| `DB_NAME` | `attendance_db` | PostgreSQL DB name (only if switching from SQLite) |
| `DB_USER` | `postgres` | PostgreSQL username |
| `DB_PASSWORD` | *(required)* | PostgreSQL password |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |

> Gmail App Password and Twilio credentials are NOT in `.env` — they are stored in the database via the Faculty Dashboard Alert Configuration form and injected into `tasks.robot` at runtime.

---

## 10. Complete Setup Guide (Fresh Machine)

### Prerequisites
- Python 3.10 or higher
- Google Chrome browser installed
- `cmake` (required to compile dlib for face recognition)
- A webcam (for face recognition features)

### Step 1 — Install system dependencies

macOS:
```bash
brew install cmake
```

Ubuntu/Debian:
```bash
sudo apt-get install cmake build-essential
```

Windows:
- Install CMake from https://cmake.org/download/
- Install Visual Studio Build Tools

---

### Step 2 — Open the project folder

```bash
cd "RPA Project"
```

---

### Step 3 — Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# OR
.venv\Scripts\activate          # Windows
```

---

### Step 4 — Install all dependencies

```bash
pip install -r requirements.txt
```

> WARNING: dlib and face_recognition take several minutes to compile. This is normal. Do NOT interrupt it.

---

### Step 5 — Set up the environment file

```bash
cp .env.example .env
# Edit .env and fill in your SECRET_KEY at minimum
```

---

### Step 6 — Run database migrations

```bash
cd web_app
python manage.py migrate
```

---

### Step 7 — Create a superuser (admin)

```bash
python manage.py createsuperuser
```

Enter a username, email, and password. This account will be used to approve faculty registrations.

---

### Step 8 — Add face photos for students

Place one photo per student in `face_recognition/known_faces/`. The filename MUST match the enrollment number exactly:

```
face_recognition/known_faces/
├── ENR2024001.jpg
├── ENR2024002.jpg
└── ...
```

- Accepted formats: `.jpg`, `.jpeg`, `.png`
- One clear face per photo
- Good lighting recommended

---

### Step 9 — ChromeDriver (for RPA Bot)

ChromeDriver is installed automatically by `webdriver-manager` (already in `requirements.txt`). No manual action needed.

---

## 11. How to Run the Project

### Start the Django Web Server

```bash
# Make sure you are in the project root with venv active
source .venv/bin/activate

cd web_app
python manage.py runserver
```

Server starts at: http://127.0.0.1:8000/

### Pages available:

| Page | URL |
|---|---|
| Landing / Home | http://127.0.0.1:8000/ |
| Student Login | http://127.0.0.1:8000/student/login/ |
| Faculty Login | http://127.0.0.1:8000/faculty/login/ |
| Faculty Register | http://127.0.0.1:8000/faculty/register/ |
| Django Admin | http://127.0.0.1:8000/admin/ |

### Approve a Faculty Account (via Django Admin)

1. Go to http://127.0.0.1:8000/admin/
2. Log in with your superuser credentials
3. Go to **Core → Faculty profiles** → find the pending faculty
4. Check `is_approved = True`
5. Go to **Auth → Users** → find the faculty's user → set `is_active = True` and `is_staff = True`
6. Save — the faculty can now log in

---

### Run Daily Attendance Reconciliation (Management Command)

Ensures students who did not attend receive an explicit `Absent` record so attendance percentages accurately reflect reality rather than remaining stuck at 100%:

```bash
# Reconcile today's attendance for all students:
python web_app/manage.py reconcile_attendance

# Or reconcile for a specific historical date:
python web_app/manage.py reconcile_attendance --date 2026-09-20
```

---

### Bulk Sync Face Encodings to Database

Extracts 128-dimensional face vectors from all photos in `face_recognition/known_faces/` and stores them directly into `Student.face_encoding` in SQLite:

```bash
python web_app/manage.py sync_face_encodings
```

*(Note: Faculty can also upload face photos directly in the web portal under **Faculty Dashboard → Students Tab → Add Student**, which computes and saves the face encoding automatically!)*

---

### Run the Classroom Face Scanner

> Make sure the Django server is also running in a separate terminal.

```bash
# From project root, with venv active
python face_recognition/scanner.py
```

- A webcam window opens titled "Classroom Attendance Scanner"
- Green box = recognised student (attendance marked)
- Red box = unknown face
- Uses frame-skipping (1 in 3 frames) and in-memory DB caching to maintain high FPS and zero DB locking
- Press `q` to quit

---

## 12. How to Run the RPA Bot

### Prerequisites
1. Django server must be running (`python web_app/manage.py runserver`)
2. Alert Configuration must be saved in the Faculty Dashboard (Gmail address + App Password)
3. Google Chrome must be installed

### Method 1 — One-Click Script with Zero-Disk Mutation (Recommended)

```bash
# From project root, with venv active:
bash run_rpa_bot.sh

# Or run in HEADLESS mode (no Chrome window, ideal for CI/CD or background execution):
bash run_rpa_bot.sh --headless
```

**Security & Architecture Guarantee:**
- The script queries the database, decrypts passwords using AES-128 Fernet in memory, and passes them securely to Robot Framework via runtime CLI flags (`--variable GMAIL_USER:...`).
- `tasks.robot` on disk is **NEVER** modified, preserving clean source control and preventing credential leakage.

What you will see in terminal:
```
========================================================
  STEP 1 — Reading secure credentials from Database
========================================================
  Gmail User : faculty@gmail.com
  SMS Enabled: True
  Threshold  : 75.0%
  Headless   : False
  Status     : Ready (source files remain clean on disk)

========================================================
  STEP 2 — Running Robot Framework RPA Bot
========================================================

╔══════════════════════════════════════════════════════╗
║  STEP 1 ▶  Opening Faculty Web Portal                ║
╚══════════════════════════════════════════════════════╝
```

Chrome will open (unless running in `--headless` mode) and you can watch every step:
- Orange border highlights the element about to be interacted with
- Fields fill in visibly one character at a time
- Table rows are highlighted as each student is processed
- Full report opens in browser when done

### Method 2 — Run Robot Framework directly

```bash
cd rpa_bot
robot --outputdir /tmp/rpa_results \
      --variable GMAIL_USER:your_email@gmail.com \
      --variable GMAIL_PASS:your_app_password \
      --variable THRESHOLD:75.0 \
      tasks.robot
```

### Viewing the RPA Report

After a run, the HTML report is at:
```
/tmp/rpa_results/report.html
```

It shows pass/fail for every step, timing, logs, and screenshots.

### Adjusting Bot Speed

In `rpa_bot/tasks.robot`, line 13:
```
Suite Setup    Set Selenium Speed    1.0s    ← change this value
```

- `1.0s` — comfortable to watch (default)
- `0.5s` — faster
- `2.0s` — slow, great for demos/presentations
- `0s` — full speed (original behaviour)

---

## 13. Gmail App Password Setup

The bot sends email via Gmail SMTP. You CANNOT use your normal Gmail password — you need an App Password.

1. Go to your Google Account → Security
2. Enable 2-Step Verification (required for App Passwords)
3. Go to Security → 2-Step Verification → App passwords
4. Select app: Mail / device: Other → name it "Attendance Bot"
5. Google generates a 16-character password like `abcd efgh ijkl mnop`
6. Copy it and paste it into the Faculty Dashboard → Alert Configuration → "Gmail App Password"

> Store this in the dashboard, NOT in your `.env` file or anywhere in the code.

---

## 14. Twilio SMS Setup (Optional)

1. Create a free account at https://www.twilio.com/
2. Get a Twilio phone number (free trial gives you one)
3. Find your Account SID and Auth Token on the Twilio Console dashboard
4. Enter them in Faculty Dashboard → Alert Configuration → Twilio section
5. Enable "SMS Alerts Enabled" toggle

> Trial account limitation: You can only send SMS to verified numbers. Go to Twilio Console → Verified Caller IDs to add test phone numbers.

Phone number format: The bot automatically adds +91 prefix for Indian numbers without country code. For other countries, enter numbers in full E.164 format (e.g., +12025551234).

---

## 15. Common Errors and Fixes

### dlib or face_recognition install fails

```
Error: cmake not found
```

Fix: Install cmake first — `brew install cmake` (macOS) or `sudo apt install cmake` (Linux)

---

### No module named face_recognition

Fix: Make sure you are in the virtual environment:
```bash
source .venv/bin/activate
pip install face_recognition
```

---

### ChromeDriver version mismatch

```
SessionNotCreatedException: This version of ChromeDriver only supports Chrome version XX
```

Fix: `webdriver-manager` should handle this automatically. If not:
```bash
pip install --upgrade webdriver-manager selenium
```

---

### Faculty login fails — "awaiting approval"

Fix: Log in as superuser at `/admin/` → approve the faculty profile. See Section 11.

---

### Gmail SMTP authentication error

```
SMTPAuthenticationError: 535 Application-specific password required
```

Fix: You must use a Gmail App Password, not your regular password. See Section 13.

---

### Face not detected / wrong person matched

- Ensure the photo in `known_faces/` is clear with good lighting
- Photo filename must exactly match enrollment number (case-sensitive)
- Only one face per photo
- Distance threshold is 0.6 — lower = stricter (fewer false positives, more misses)

---

### AttendanceRecord duplicate / already marked

This is by design — `get_or_create()` prevents double-marking. A student can only be marked once per day.

---

### RPA bot says "No alert configuration found"

Fix: Log in to the Faculty Dashboard → Alert Config tab → enter Gmail credentials → click "Save Configuration". Then run the bot again.

---

### Attendance dates are wrong (off by one day)

Already fixed — the Django timezone is set to Asia/Kolkata (IST) in `settings.py`:
```python
TIME_ZONE = 'Asia/Kolkata'
```

---

## Notes for Developers

- **Database:** SQLite is used by default (zero configuration). To switch to PostgreSQL, update `DATABASES` in `settings.py` and fill in the `.env` DB variables.
- **Logs:** RPA bot run logs are saved to `/tmp/rpa_debug.log` and also printed to the Django console.
- **Security:** Never commit `.env` or `tasks.robot` when it has real credentials. The `run_rpa_bot.sh` script resets credentials after every run automatically.
- **Face Encoding Cache:** The face encoding cache lives in memory. It reloads on server restart or when `invalidate_cache()` is called (triggered automatically when a new student is added via the dashboard).
- **RPA vs Python alerts:** The "Send Alerts Now" button in the dashboard uses pure Python (no browser, no Robot Framework needed). The `bash run_rpa_bot.sh` approach uses the full RPA browser automation and is best for demonstrations or when you want to visually verify the process.

---

*Built by Sanyam Gehlot — Facial Recognition Automated Attendance System with RPA Alert Bot*
