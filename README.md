<div align="center">

<h1>🎓 Facial Recognition Automated Attendance System</h1>
<h3><i>with RPA-Powered Low-Attendance Alerts via Email & SMS</i></h3>

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Robot Framework](https://img.shields.io/badge/Robot_Framework-7.4-000000?style=for-the-badge&logo=robotframework&logoColor=white)](https://robotframework.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-5.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![Twilio](https://img.shields.io/badge/Twilio-SMS-F22F46?style=for-the-badge&logo=twilio&logoColor=white)](https://twilio.com)

<br/>

**A full-stack university attendance management platform** combining real-time facial recognition with a Robotic Process Automation (RPA) bot that monitors attendance and automatically alerts parents via Email and SMS when a student falls below the threshold.

<br/>

[✨ Features](#-features) · [🏗 Architecture](#-system-architecture) · [📦 Installation](#-installation) · [🚀 Usage](#-usage-guide) · [⚙️ Configuration](#-configuration) · [📁 Structure](#-project-structure)

---

</div>

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Face Recognition Login** | Students authenticate via webcam — real-time dlib face encoding |
| 🆔 **Enrollment Number Login** | Alternative text-based login for students |
| 📊 **Live Attendance Dashboard** | Students view attendance %, full history & leave status |
| 🏛️ **Faculty Admin Portal** | Full student CRUD, leave approval/rejection, alert management |
| 🤖 **One-Click RPA Alert Bot** | Faculty clicks a button → bot instantly scans all students & fires alerts |
| 📧 **Email Alerts** | Gmail SMTP warning dispatched to parent email |
| 📱 **SMS Alerts** | Twilio SMS fired to parent phone (E.164 auto-formatted) |
| 🌙 **Dark / Light Theme** | Persistent monochromatic theme toggle across all pages |
| 📋 **Leave Management** | Students apply for leave; faculty approve/reject |
| 🔐 **Role-Based Auth** | Separate secure flows for Students and Faculty |
| 🛡️ **Django Admin** | Superuser panel to approve faculty and manage all data |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Student Portal                        │
│                                                             │
│   [Webcam Face Scan] ──────► Mark Attendance Automatically  │
│   [Enrollment No.]  ──────► Manual Login → Dashboard        │
│                                                             │
│   Dashboard: Attendance % · History · Apply Leave           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Django Backend    │
                    │   SQLite Database   │
                    └──────────┬──────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                      Faculty Portal                          │
│                                                             │
│  ┌─ Students ──┐  ┌─ Leaves ──┐  ┌─ Alert Config ──┐      │
│  │ Add/Delete  │  │ Approve/  │  │ Gmail + Twilio  │      │
│  │ Set email/  │  │ Reject    │  │ Threshold %     │      │
│  │ phone       │  └───────────┘  └────────┬────────┘      │
│  └─────────────┘                          │                 │
│                               ┌───────────▼──────────┐     │
│                               │  ▶ Run Alert Bot Now  │     │
│                               └───────────┬──────────┘     │
└───────────────────────────────────────────┼────────────────┘
                                            │
                    ┌───────────────────────▼────────────────────────┐
                    │           Direct Python Alert Engine            │
                    │                                                │
                    │  1. Query DB → find students below threshold   │
                    │  2. Connect Gmail SMTP → send parent email     │
                    │  3. Connect Twilio API → send parent SMS       │
                    │  4. Return per-student results to dashboard    │
                    └────────────────────────────────────────────────┘
```

> **Note:** The RPA bot (`rpa_bot/tasks.robot`) can also be run directly from the terminal using Robot Framework + Selenium for demo/testing purposes.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Django 6.0 (Python 3.10+) + SQLite |
| **Face Recognition** | `face_recognition` (dlib) + OpenCV 5 + Pillow |
| **RPA Automation** | Robot Framework 7.4 + SeleniumLibrary + ChromeDriver |
| **Email Alerts** | Python `smtplib` (Gmail SMTP + App Password) |
| **SMS Alerts** | Twilio REST API (`twilio` Python SDK) |
| **Frontend** | Vanilla HTML/CSS/JS — Dark/Light theme, glassmorphism cards |

---

## 📦 Installation

### Prerequisites

- Python 3.10+
- Google Chrome (for the terminal Robot Framework demo)
- A Gmail account with [App Password](https://myaccount.google.com/apppasswords) enabled
- A [Twilio](https://twilio.com) account (free trial works)

### Step 1: Clone

```bash
git clone https://github.com/Awesome-sanyam/Facial-recognition-automated-attendence-system-with-alert.git
cd Facial-recognition-automated-attendence-system-with-alert
```

### Step 2: Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Database Setup

```bash
cd web_app
python manage.py migrate
python manage.py createsuperuser
# Enter username: admin  |  password: admin
```

### Step 5: Run

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000** 🚀

---

## 🚀 Usage Guide

### 🎓 Student Flow

| Step | Action |
|---|---|
| 1 | Go to `http://127.0.0.1:8000` → **Student Portal** |
| 2 | **Face Login** — click "Scan Face", allow camera, recognized automatically |
| 3 | **OR** enter your **Enrollment Number** manually |
| 4 | View your Attendance %, full history, and submit leave applications |

### 🏛️ Faculty Flow

| Step | Action |
|---|---|
| 1 | `http://127.0.0.1:8000/faculty/register/` → Register faculty account |
| 2 | `http://127.0.0.1:8000/admin/` → Login as `admin/admin` → Approve the faculty |
| 3 | `http://127.0.0.1:8000/faculty/login/` → Faculty login |
| 4 | **Students tab** → Add students with parent email & phone |
| 5 | **Alert Configuration tab** → Enter Gmail + Twilio credentials → **Save** |
| 6 | Click **"▶ Run Alert Bot Now"** → emails & SMS fire instantly |

### 🤖 Terminal Bot (Demo / Testing)

```bash
cd rpa_bot
robot tasks.robot
```

This opens Chrome, logs into Django Admin, scans all student rows, and dispatches alerts to anyone below 75%.

### 📸 Register Student Faces

```bash
cd face_recognition
python scanner.py
# Follow the on-screen prompts to capture and encode a student's face
```

---

## ⚙️ Configuration

### Gmail — App Password Setup

1. Enable **2-Step Verification** on your Google Account
2. Go to → [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create an App Password for "Mail"
4. Copy the 16-character password
5. Paste into Faculty Dashboard → **Alert Configuration**

### Twilio — SMS Setup

1. Sign up free at [twilio.com](https://twilio.com)
2. From the Console, copy:
   - **Account SID** (starts with `AC...`)
   - **Auth Token**
   - A **Twilio Phone Number** (e.g. `+1XXXXXXXXXX`)
3. Paste all three into Faculty Dashboard → **Alert Configuration**

> **Trial Account Note:** Twilio free trials can only SMS to verified numbers.  
> Verify numbers at [console.twilio.com/phone-numbers/verified](https://console.twilio.com/us1/develop/phone-numbers/manage/verified)  
> OR add $5 credit to upgrade and SMS any number worldwide instantly.

---

## 📁 Project Structure

```
📦 Facial-recognition-automated-attendence-system-with-alert
│
├── 📂 web_app/                          # Django Project Root
│   ├── 📂 core/                         # Main Application
│   │   ├── 📂 templates/core/
│   │   │   ├── home.html                # Landing — portal selection
│   │   │   ├── login.html               # Student login (face + enrollment)
│   │   │   ├── dashboard.html           # Student attendance dashboard
│   │   │   ├── apply_leave.html         # Leave application form
│   │   │   ├── faculty_login.html       # Faculty authentication
│   │   │   ├── faculty_register.html    # Faculty registration
│   │   │   └── faculty_dashboard.html   # Full faculty admin portal
│   │   ├── models.py                    # DB schema
│   │   ├── views.py                     # All business logic + alert engine
│   │   ├── urls.py                      # URL routing
│   │   └── admin.py                     # Django Admin customization
│   └── attendance_system/
│       ├── settings.py                  # Django settings
│       └── urls.py                      # Root URL conf
│
├── 📂 rpa_bot/                          # Robot Framework Bot
│   ├── tasks.robot                      # Main RPA task (terminal use)
│   ├── EmailLibrary.py                  # Custom Gmail SMTP RF library
│   └── SmsLibrary.py                    # Custom Twilio SMS RF library
│
├── 📂 face_recognition/                 # Face Recognition Module
│   ├── scanner.py                       # Capture & encode student faces
│   └── face_login.py                    # Real-time recognition for web login
│
├── requirements.txt                     # All Python dependencies (pinned)
├── .env.example                         # Environment variable template
├── .gitignore                           # Excludes venv, secrets, artifacts
└── README.md
```

---

## 🗃 Database Models

| Model | Key Fields |
|---|---|
| `Student` | `name`, `enrollment_number`, `parent_email`, `parent_phone`, `face_encoding` |
| `AttendanceRecord` | `student (FK)`, `date`, `time`, `status` (Present/Absent) |
| `LeaveApplication` | `student (FK)`, `date_requested`, `reason`, `status`, `reviewed_by` |
| `FacultyProfile` | `user (1-1)`, `department`, `phone`, `is_approved` |
| `AlertConfiguration` | `faculty (1-1)`, gmail creds, twilio creds, threshold %, template body |

---

## 🔐 Default Credentials

| Role | Username | Password | URL |
|---|---|---|---|
| Django Superuser | `admin` | `admin` | `/admin/` |
| Faculty | *(registered via portal)* | *(set on registration)* | `/faculty/login/` |

---

## 🧠 How the Alert Bot Works

```
Faculty clicks "▶ Run Alert Bot Now"
        ↓
Django reads student list from database
        ↓
For each student below threshold %:
   ├── 📧 Send Email via Gmail SMTP (smtplib)
   └── 📱 Send SMS via Twilio REST API
        ↓
Results returned to dashboard instantly:
"✅ Scanned 5 students — 4 below 75%. 4 emails sent. 1 SMS sent."
```

**No browser, no Chrome, no Selenium needed for the web trigger.** The alert engine runs entirely within Django's request lifecycle using direct Python libraries — fast, reliable, and no deadlocks.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

---

## 📄 License

This project is licensed under the **MIT License**.

---

<div align="center">

Built with ❤️ by **[Sanyam Gehlot](https://github.com/Awesome-sanyam)**

*Face Recognition · Django · Robot Framework · Twilio · OpenCV*

⭐ **Star this repo if it helped you!** ⭐

</div>
