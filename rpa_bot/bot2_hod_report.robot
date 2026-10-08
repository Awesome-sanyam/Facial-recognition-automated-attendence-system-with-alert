*** Settings ***
Documentation
...    ══════════════════════════════════════════════════════════════════
...    BOT 2 — Monthly HOD PDF Report Generator & Email Dispatcher
...    University Automated Attendance & Alert System
...    ══════════════════════════════════════════════════════════════════
...
...    PURPOSE:
...      This bot automatically generates a professional PDF report of
...      all students whose attendance is below 75% (configurable)
...      and emails it directly to the Dean/HOD.
...
...    FLOW:
...      1. Connect to the Django SQLite database.
...      2. Query all students with attendance below the threshold.
...      3. Compute each student's percentage (mirrors Django model logic).
...      4. Generate a professionally formatted PDF using Python's
...         reportlab library (pure Python, no browser required).
...      5. Email the PDF as an attachment to the Dean's configured email.
...      6. Write an audit log entry to RPABotLog.
...
...    LIBRARIES USED:
...      - RPA.Database  → Direct SQLite access (no N+1 queries)
...      - RPA.PDF       → PDF generation
...      - EmailLibrary  → SMTP Gmail attachment sending
...
...    NOTE ON PDF GENERATION:
...      Since rpaframework's RPA.PDF is primarily a *reader*, we use
...      a custom Python keyword that wraps 'reportlab' for creation.
...      This is the standard enterprise approach in RF + rpaframework.
...
...    ══════════════════════════════════════════════════════════════════

Library           DatabaseLibrary
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587
Library           ReportLibrary.py


*** Variables ***
# ── Database ──────────────────────────────────────────────────────────────────
${DB_PATH}        ${CURDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}      sqlite3

# ── Report Config ─────────────────────────────────────────────────────────────
${HOD_THRESHOLD}          ${75.0}
${REPORT_OUTPUT_DIR}      ${CURDIR}${/}reports

# ── Email Credentials (injected via --variable flags from Django view) ─────────
${GMAIL_USER}     CONFIGURE_VIA_DASHBOARD
${GMAIL_PASS}     CONFIGURE_VIA_DASHBOARD
${DEAN_EMAIL}     CONFIGURE_VIA_DASHBOARD

# ── Bot Identity ──────────────────────────────────────────────────────────────
${BOT_NAME}       hod_report


*** Tasks ***
# ══════════════════════════════════════════════════════════════════
# MAIN TASK
# ══════════════════════════════════════════════════════════════════
Generate And Email HOD Attendance Report
    [Documentation]
    ...    Full pipeline:
    ...    1. Connect to SQLite DB.
    ...    2. Query all students & compute attendance.
    ...    3. Filter students below HOD threshold.
    ...    4. Generate a PDF report using ReportLab.
    ...    5. Email the PDF to the Dean.
    ...    6. Write audit log.

    Print Banner    BOT 2 — HOD PDF REPORT    STARTED

    # ── Step 1: DB Connection ───────────────────────────────────────
    Connect To Application Database

    # ── Step 2 & 3: Fetch low-attendance students ───────────────────
    ${low_students}=    Fetch Students Below Threshold

    ${count}=    Get Length    ${low_students}
    Log To Console    📋 Found ${count} student(s) below ${HOD_THRESHOLD}% threshold.

    IF    ${count} == 0
        Log To Console    ✅ All students meet the attendance threshold — no PDF needed.
        Write Bot Log    No students below threshold. Report not generated.    ${0}    ${EMPTY}
        Pass Execution    No students below threshold.
    END

    # ── Step 4: Generate PDF ────────────────────────────────────────
    ${report_path}=    Generate PDF Report    ${low_students}    ${count}

    # ── Step 5: Email PDF to Dean ───────────────────────────────────
    IF    '${GMAIL_USER}' != 'CONFIGURE_VIA_DASHBOARD' and '${GMAIL_USER}' != '${EMPTY}' and '${DEAN_EMAIL}' != 'CONFIGURE_VIA_DASHBOARD' and '${DEAN_EMAIL}' != '${EMPTY}'
        Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
        Send HOD Report Email    ${report_path}    ${count}
        ${summary}=    Set Variable
        ...    HOD Report generated with ${count} at-risk student(s). Emailed to ${DEAN_EMAIL}.
    ELSE
        Log To Console    ℹ️ Gmail/Dean credentials not configured — skipping email dispatch. PDF saved: ${report_path}
        ${summary}=    Set Variable
        ...    HOD Report generated with ${count} at-risk student(s). PDF saved at ${report_path}. Email skipped (unconfigured).
    END

    # ── Step 6: Audit log ───────────────────────────────────────────
    Write Bot Log    ${summary}    ${count}    ${EMPTY}

    Print Banner    BOT 2 — HOD PDF REPORT    FINISHED
    Log To Console    ✅ ${summary}

    [Teardown]    Run Keywords
    ...    Disconnect From Database
    ...    AND    Close Connection


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
Connect To Application Database
    Log To Console    🗄 Connecting to SQLite: ${DB_PATH}
    Connect To Database    ${DB_MODULE}    ${DB_PATH}
    Execute Sql String    PRAGMA journal_mode=WAL
    Execute Sql String    PRAGMA busy_timeout=5000
    Log To Console    ✅ DB connected — WAL mode, 5s busy-timeout active.


# ══════════════════════════════════════════════════════════════════
# Fetch all students with computed attendance below threshold.
# Uses a single SQL subquery to avoid N+1 — mirrors the Django
# annotate() approach used in views.py faculty_dashboard.
# ══════════════════════════════════════════════════════════════════
Fetch Students Below Threshold
    [Documentation]
    ...    Returns a list of tuples:
    ...    (name, enrollment_number, department, year, parent_email, pct)
    ...    Only students whose computed attendance < HOD_THRESHOLD.

    ${sql}=    Catenate    SEPARATOR=\n
    ...    SELECT
    ...        s.name,
    ...        s.enrollment_number,
    ...        s.department,
    ...        s.year,
    ...        s.parent_email,
    ...        CASE
    ...            WHEN countable.cnt = 0 THEN 100.0
    ...            ELSE ROUND(
    ...                CAST(present.cnt AS REAL) / CAST(countable.cnt AS REAL) * 100, 2
    ...            )
    ...        END AS attendance_pct
    ...    FROM core_student s
    ...    LEFT JOIN (
    ...        SELECT student_id, COUNT(*) as cnt
    ...        FROM core_attendancerecord
    ...        WHERE status != 'Excused'
    ...        GROUP BY student_id
    ...    ) AS countable ON countable.student_id = s.id
    ...    LEFT JOIN (
    ...        SELECT student_id, COUNT(*) as cnt
    ...        FROM core_attendancerecord
    ...        WHERE status = 'Present'
    ...        GROUP BY student_id
    ...    ) AS present ON present.student_id = s.id
    ...    WHERE
    ...        countable.cnt IS NOT NULL AND
    ...        (CAST(present.cnt AS REAL) / CAST(countable.cnt AS REAL) * 100) < ${HOD_THRESHOLD}
    ...    ORDER BY attendance_pct ASC

    ${result}=    Query    ${sql}
    RETURN    ${result}


# ══════════════════════════════════════════════════════════════════
# Generate a professional PDF report using ReportLab.
# Returns the absolute file path of the generated PDF.
# ══════════════════════════════════════════════════════════════════
Generate PDF Report
    [Documentation]
    ...    Creates a formatted PDF at ${REPORT_OUTPUT_DIR}/HOD_Report_<date>.pdf
    ...    Uses ReportLibrary with ReportLab SimpleDocTemplate and styled Table.
    [Arguments]    ${students}    ${count}

    # Ensure the output directory exists
    Create Directory    ${REPORT_OUTPUT_DIR}

    ${today}=    Get Current Date    result_format=%Y-%m-%d
    ${report_filename}=    Set Variable    HOD_Report_${today}.pdf
    ${report_path}=    Join Path    ${REPORT_OUTPUT_DIR}    ${report_filename}

    # Call native Python ReportLibrary keyword
    Generate Hod Pdf Report    ${report_path}    ${students}    ${HOD_THRESHOLD}    ${today}

    Log To Console    📄 PDF Report generated: ${report_path}
    RETURN    ${report_path}


# ══════════════════════════════════════════════════════════════════
# Send the PDF as an email attachment to the Dean.
# ══════════════════════════════════════════════════════════════════
Send HOD Report Email
    [Documentation]    Emails the PDF report to the Dean using Gmail SMTP.
    [Arguments]    ${pdf_path}    ${count}

    ${today}=    Get Current Date    result_format=%B %Y
    ${subject}=    Set Variable    [Monthly Report] ${count} At-Risk Students — ${today}
    ${body}=    Catenate    SEPARATOR=\n
    ...    Dear Dean / Head of Department,\n\n
    ...    Please find attached the automated Monthly Attendance Risk Report for ${today}.\n\n
    ...    SUMMARY:\n
    ...    • Total students flagged below 75% attendance: ${count}\n
    ...    • Report generated automatically by the University RPA Bot.\n\n
    ...    This report was generated on: ${today}.\n
    ...    Please review and take necessary action for students at risk.\n\n
    ...    Regards,\n
    ...    University RPA Attendance System\n
    ...    [This is an automated message — do not reply]

    Log To Console    📧 Sending HOD Report to: ${DEAN_EMAIL}

    TRY
        Send Message
        ...    sender=${GMAIL_USER}
        ...    recipients=${DEAN_EMAIL}
        ...    subject=${subject}
        ...    body=${body}
        ...    attachments=${pdf_path}
        Log To Console    ✅ HOD Report emailed to: ${DEAN_EMAIL}
    EXCEPT    AS    ${err}
        Log To Console    ❌ Failed to email HOD Report: ${err}
        Log    HOD Report email failed: ${err}    ERROR
        Fail    HOD Report email failed: ${err}
    END


# ══════════════════════════════════════════════════════════════════
Write Bot Log
    [Arguments]    ${summary}    ${records}    ${errors}
    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S
    ${status}=    Set Variable If    '${errors}' == '${EMPTY}'    success    partial
    TRY
        ${sql_log}=    Catenate    SEPARATOR=\n
        ...    INSERT INTO core_rpabotlog
        ...        (bot_name, status, started_at, finished_at, summary, records_processed, errors, triggered_by_id)
        ...    VALUES
        ...        ('${BOT_NAME}', '${status}', '${now}', '${now}',
        ...         '${summary}', ${records}, '${errors}', NULL)
        Execute Sql String    ${sql_log}
        Log To Console    📝 Audit log written.
    EXCEPT    AS    ${err}
        Log To Console    ⚠️ Could not write audit log: ${err}
    END


Print Banner
    [Arguments]    ${title}    ${state}
    Log To Console    \n======================================================
    Log To Console    [${title} -- ${state}]
    Log To Console    ======================================================

