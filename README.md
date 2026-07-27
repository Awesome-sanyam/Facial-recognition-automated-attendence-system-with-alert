<div align="center">

# 🎓 Facial Recognition Automated Attendance System
### *with RPA-powered Low-Attendance Alerts via Email & SMS*

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Robot Framework](https://img.shields.io/badge/Robot_Framework-7.4-000000?style=for-the-badge&logo=robotframework&logoColor=white)](https://robotframework.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-5.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![Twilio](https://img.shields.io/badge/Twilio-SMS-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)

**A complete, production-ready university attendance management platform** combining real-time facial recognition with a Robotic Process Automation (RPA) bot to monitor attendance and automatically alert parents/students via Email and SMS.

[Features](#-features) · [Architecture](#-system-architecture) · [Installation](#-installation) · [Usage](#-usage-guide) · [Screenshots](#-project-structure)

---

</div>

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Facial Recognition Login** | Students authenticate via webcam — no passwords, no IDs |
| 📊 **Real-time Attendance Dashboard** | Students view their attendance %, history, and leave status live |
| 🏛️ **Faculty Admin Portal** | Full CRUD for students, approve/reject leaves, configure alerts |
| 🤖 **RPA Alert Bot** | Robot Framework bot auto-scans Django Admin and sends targeted alerts |
| 📧 **Email Alerts** | Gmail SMTP alerts dispatched to parent email on low attendance |
| 📱 **SMS Alerts** | Twilio SMS fired to parent phone number in E.164 format |
| 🌙 **Light / Dark Theme** | System-wide monochromatic premium UI with persistent theme toggle |
| 🔐 **Multi-role Auth** | Separate secure login flows for Students (face/ID) and Faculty |
| 📋 **Leave Management** | Students apply for leave; faculty approve/reject via the dashboard |
| 🛡️ **Django Admin** | Superuser panel to approve faculty registrations and view all data |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────┐
│                   Student Portal                │
│  Face Recognition Login ──► Attendance Marked  │
│  Enrollment Number Login ──► Dashboard View    │
└──────────────────────┬──────────────────────────┘
                       │
              ┌────────▼────────┐
              │   Django Backend │
              │   (SQLite DB)    │
              └────────┬─────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│                Faculty Admin Portal             │
│  Manage Students · Approve Leaves · Config Bot  │
│                  ▼ clicks "Run Bot"             │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │     Robot Framework Bot     │
        │  1. Opens Chrome            │
        │  2. Logs into Django Admin  │
        │  3. Scans all students      │
        │  4. IF attendance < 75%:    │
        │     ├── Send Email (Gmail)  │
        │     └── Send SMS (Twilio)   │
        └─────────────────────────────┘
```

---

## 🛠 Tech Stack

- **Backend:** Django 6.0 (Python) + SQLite
- **Face Recognition:** `face_recognition` (dlib) + OpenCV + Pillow
- **RPA / Automation:** Robot Framework 7.4 + SeleniumLibrary + ChromeDriver
- **Email:** Python `smtplib` (Gmail SMTP with App Password)
- **SMS:** Twilio REST API (via `twilio` Python SDK)
- **Frontend:** Vanilla HTML/CSS/JS — premium dark/light theme, glassmorphism cards

---

## 📦 Installation

### Prerequisites
- Python 3.10+
- Google Chrome browser
- ChromeDriver (matching your Chrome version)
- A Gmail account with an [App Password](https://myaccount.google.com/apppasswords) enabled
- A [Twilio](https://twilio.com) account (free trial works for verified numbers)

### Step 1: Clone & Setup

```bash
git clone https://github.com/Awesome-sanyam/Facial-recognition-automated-attendence-system-with-alert-system.git
cd Facial-recognition-automated-attendence-system-with-alert-system
```

### Step 2: Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup the Database

```bash
cd web_app
python manage.py migrate
python manage.py createsuperuser   # Use username: admin, password: admin
```

### Step 5: Run the Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000** 🚀

---

## 🚀 Usage Guide

### 🎓 Student Flow

1. Go to **http://127.0.0.1:8000** → Student Portal
2. **Option A:** Click **"Scan Face"** — allow camera access, face is recognized automatically
3. **Option B:** Enter your enrollment number manually
4. View your **Attendance %, History**, and submit **Leave Applications**

### 🏛️ Faculty Flow

1. Go to **http://127.0.0.1:8000/faculty/register/** → Register as faculty
2. Login to **http://127.0.0.1:8000/admin/** with `admin/admin` → Approve the faculty account
3. Login at **http://127.0.0.1:8000/faculty/login/**
4. **Add students**, set parent email/phone, manage leaves
5. Configure **Gmail SMTP** and **Twilio SMS** settings under the **Alert Configuration** tab
6. Click **"▶ Run Alert Bot Now"** to dispatch alerts to all low-attendance students

### 🤖 Direct Bot Execution

```bash
cd rpa_bot
robot tasks.robot
```

### 📸 Face Registration (Admin Only)

```bash
cd face_recognition
python scanner.py
```

---

## ⚙️ Configuration

### Gmail Setup
1. Enable 2-Factor Authentication on your Google Account
2. Generate an **App Password** at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Enter the email + 16-character app password in the Faculty Alert Config

### Twilio SMS Setup
1. Sign up at [twilio.com](https://twilio.com)
2. Get your **Account SID**, **Auth Token**, and a **Twilio Phone Number**
3. For Trial accounts: verify recipient numbers at [twilio.com/user/account/phone-numbers/verified](https://www.twilio.com/user/account/phone-numbers/verified)
4. Enter credentials in the Faculty Alert Config → save → run bot

> **Note:** Upgrade your Twilio account with a small credit (~$5) to send SMS to any number worldwide without manual verification.

---

## 📁 Project Structure

```
📦 RPA Project
├── 📂 web_app/                      # Django application
│   ├── 📂 core/                     # Main app module
│   │   ├── 📂 templates/core/       # All HTML templates
│   │   │   ├── home.html            # Landing page (portal selection)
│   │   │   ├── login.html           # Student login (face + manual)
│   │   │   ├── dashboard.html       # Student attendance dashboard
│   │   │   ├── apply_leave.html     # Leave application form
│   │   │   ├── faculty_login.html   # Faculty auth
│   │   │   ├── faculty_register.html# Faculty registration
│   │   │   ├── faculty_dashboard.html # Full admin dashboard
│   │   │   └── _theme_css.html      # Shared CSS variables (light/dark)
│   │   ├── models.py                # DB models (Student, Attendance, Leave…)
│   │   ├── views.py                 # All business logic + RPA trigger
│   │   ├── urls.py                  # URL routing
│   │   └── admin.py                 # Django Admin customization
│   └── attendance_system/           # Django settings & WSGI
│
├── 📂 rpa_bot/                      # Robot Framework automation
│   ├── tasks.robot                  # Main RPA task definition
│   ├── EmailLibrary.py              # Custom Gmail SMTP library
│   └── SmsLibrary.py                # Custom Twilio SMS library
│
├── 📂 face_recognition/             # Facial recognition module
│   ├── scanner.py                   # Face capture & encoding registration
│   └── face_login.py                # Real-time recognition for web login
│
├── requirements.txt                 # All Python dependencies
└── .gitignore
```

---

## 🔐 Admin Credentials

| Role | Username | Password | URL |
|---|---|---|---|
| Django Superuser | `admin` | `admin` | `/admin/` |
| Faculty | *(registered via portal)* | *(set during registration)* | `/faculty/login/` |

---

## 🧠 How the RPA Bot Works

1. **Triggered** — Faculty clicks "Run Bot" on the dashboard (or run `robot tasks.robot` directly)
2. **Credential sync** — Django writes the saved Twilio/Gmail config into `tasks.robot` automatically before launching
3. **Browser open** — Selenium opens Chrome and logs into Django Admin (`/admin/core/student/`)
4. **Audit** — Iterates every student row, reads name, parent email, phone, and attendance %
5. **Alert logic** — If attendance < threshold (default 75%):
   - 📧 Sends a warning email to parent email via Gmail SMTP
   - 📱 Sends an SMS to parent phone via Twilio (auto-formats to E.164 for Indian numbers)
6. **Result** — Success/error message displayed back on the Faculty Dashboard

---

## 📊 Database Models

| Model | Key Fields |
|---|---|
| `Student` | name, enrollment_number, parent_email, parent_phone, face_encoding |
| `AttendanceRecord` | student (FK), date, time, status (Present/Absent) |
| `LeaveApplication` | student (FK), date_requested, reason, status, reviewed_by |
| `FacultyProfile` | user (1-1), department, phone, is_approved |
| `AlertConfiguration` | faculty (1-1), gmail credentials, twilio credentials, thresholds |

---

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">

Built with ❤️ by **Sanyam Gehlot** · [GitHub](https://github.com/Awesome-sanyam)

*Facial Recognition + RPA + Django + Twilio = Smart University Attendance*

</div>
