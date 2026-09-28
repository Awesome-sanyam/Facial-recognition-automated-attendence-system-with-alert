*** Settings ***
Documentation
...    ══════════════════════════════════════════════════════════════════
...    BOT 4 — PTM (Parent-Teacher Meeting) Escalation Bot
...    University Automated Attendance & Alert System
...    ══════════════════════════════════════════════════════════════════
...
...    PURPOSE:
...      This bot finds all students with attendance BELOW 50% and
...      sends a formal, professionally worded Parent-Teacher Meeting
...      invitation email to the student's registered parent email.
...
...    THIS IS A CRITICAL ESCALATION —  50% is severe and requires
...    direct parental intervention through a scheduled PTM.
...
...    FLOW:
...      1. Connect to the Django SQLite database.
...      2. Query all students below the 50% PTM threshold using an
...         optimised SQL subquery (no N+1 queries).
...      3. For each student, send a formal PTM invitation email.
...      4. Log every sent email to the console and audit log.
...      5. Write final audit entry to RPABotLog.
...
...    EMAIL DESIGN:
...      The PTM email is formal and professional — designed to be
...      printed or forwarded to school administration if needed.
...      It includes the student's current attendance percentage,
...      a formal salutation, and a request to schedule a meeting.
...
...    ══════════════════════════════════════════════════════════════════

Library           DatabaseLibrary
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587


*** Variables ***
# ── Database ──────────────────────────────────────────────────────────────────
${DB_PATH}            ${CURDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}          sqlite3

# ── PTM Escalation Config ─────────────────────────────────────────────────────
# Students BELOW this percentage will receive a PTM invite.
${PTM_THRESHOLD}      ${50.0}

# ── Email Credentials (injected via --variable flags from Django view) ─────────
${GMAIL_USER}         CONFIGURE_VIA_DASHBOARD
${GMAIL_PASS}         CONFIGURE_VIA_DASHBOARD

# ── Institution Branding ──────────────────────────────────────────────────────
${INSTITUTION_NAME}   University Attendance System
${ADMIN_CONTACT}      administration@university.edu

# ── Email Template ─────────────────────────────────────────────────────────────
${PTM_SUBJECT}        URGENT: Parent-Teacher Meeting Required — {student_name}

# ── Bot Identity ──────────────────────────────────────────────────────────────
${BOT_NAME}           ptm_escalation


*** Tasks ***
# ══════════════════════════════════════════════════════════════════
# MAIN TASK
# ══════════════════════════════════════════════════════════════════
Send PTM Escalation Invites
    [Documentation]
    ...    Full PTM escalation pipeline:
    ...    1. Connect to DB.
    ...    2. Find all students < 50% attendance.
    ...    3. Authorise Gmail SMTP.
    ...    4. For each critical student, send formal PTM invite.
    ...    5. Write audit log.

    Print Banner    BOT 4 — PTM ESCALATION    STARTED

    # Step 1: Connect to DB
    Connect To Application Database

    # Step 2: Fetch students below PTM threshold
    ${critical_students}=    Fetch Students Below PTM Threshold

    ${count}=    Get Length    ${critical_students}
    Log To Console    🚨 Found ${count} student(s) below ${PTM_THRESHOLD}% — PTM escalation required.

    IF    ${count} == 0
        Log To Console    ✅ No students below ${PTM_THRESHOLD}% — PTM escalation not required.
        Write Bot Log    No students below PTM threshold. No emails sent.    ${0}    ${EMPTY}
        Pass Execution    No students below PTM threshold.
    END

    # Step 3: Authorise Gmail SMTP
    Log To Console    📧 Connecting to Gmail SMTP as: ${GMAIL_USER}
    Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
    Log To Console    ✅ Gmail SMTP authorised.

    # Step 4: Send PTM invite to each critical student's parent
    ${sent_count}=    Set Variable    ${0}
    ${errors}=        Set Variable    ${EMPTY}

    FOR    ${student}    IN    @{critical_students}
        ${result}=    Send PTM Invite    ${student}
        IF    '${result}' == 'sent'
            ${sent_count}=    Evaluate    ${sent_count} + 1
        ELSE
            ${errors}=    Set Variable    ${errors} | Failed: ${student[0]}
        END
        # Brief pause between emails to avoid SMTP rate limiting
        Sleep    0.5s
    END

    # Step 5: Audit log
    ${summary}=    Set Variable
    ...    PTM Escalation: ${count} critical students found. ${sent_count} PTM invite(s) emailed to parents.
    Write Bot Log    ${summary}    ${sent_count}    ${errors}

    Print Banner    BOT 4 — PTM ESCALATION    FINISHED
    Log To Console    ✅ ${summary}

    [Teardown]    Run Keywords
    ...    Disconnect From Database
    ...    AND    Close Connection


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
Connect To Application Database
    Log To Console    🗄 Connecting to SQLite: ${DB_PATH}
    Connect To Database    ${DB_MODULE}    ${DB_PATH}
    Log To Console    ✅ DB connected.


# ══════════════════════════════════════════════════════════════════
# Fetch all students below the PTM threshold (< 50%).
# Uses the same optimised SQL subquery pattern as Bot 2.
# Returns: list of (name, enrollment_number, department, year,
#                   parent_email, parent_phone, attendance_pct)
# ══════════════════════════════════════════════════════════════════
Fetch Students Below PTM Threshold
    [Documentation]    Returns students with computed attendance < ${PTM_THRESHOLD}%.
    ${sql}=    Catenate    SEPARATOR=\n
    ...    SELECT
    ...        s.name,
    ...        s.enrollment_number,
    ...        s.department,
    ...        s.year,
    ...        s.parent_email,
    ...        s.parent_phone,
    ...        CASE
    ...            WHEN countable.cnt IS NULL OR countable.cnt = 0 THEN 0.0
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
    ...        (CAST(COALESCE(present.cnt, 0) AS REAL) / CAST(countable.cnt AS REAL) * 100) < ${PTM_THRESHOLD}
    ...    ORDER BY attendance_pct ASC

    ${result}=    Query    ${sql}
    RETURN    ${result}


# ══════════════════════════════════════════════════════════════════
# Send PTM Invite
# Sends a single formal PTM invitation email to the student's parent.
# Returns: 'sent' or 'failed'
# ══════════════════════════════════════════════════════════════════
Send PTM Invite
    [Documentation]    Constructs and sends a formal PTM invite email.
    [Arguments]    ${student_row}

    ${name}=          Set Variable    ${student_row[0]}
    ${enr}=           Set Variable    ${student_row[1]}
    ${department}=    Set Variable    ${student_row[2]}
    ${year}=          Set Variable    ${student_row[3]}
    ${parent_email}=  Set Variable    ${student_row[4]}
    ${pct}=           Set Variable    ${student_row[6]}

    Log To Console    \n── PTM Invite: ${name} (${pct}%) → ${parent_email}

    # Build formal PTM email body
    ${subject}=    Replace String    ${PTM_SUBJECT}    {student_name}    ${name}
    ${body}=    Catenate    SEPARATOR=\n
    ...    Dear Parent / Guardian of ${name},
    ...
    ...    We are writing to formally inform you that ${name} (Enrollment: ${enr}),
    ...    currently enrolled in ${department} — Year ${year}, has an attendance
    ...    percentage of ${pct}%, which is critically below the minimum requirement of 75%.
    ...
    ...    ───────────────────────────────────────────────────
    ...    STUDENT DETAILS
    ...    Name              : ${name}
    ...    Enrollment Number : ${enr}
    ...    Department        : ${department}
    ...    Current Year      : Year ${year}
    ...    Current Attendance: ${pct}%  (Minimum Required: 75%)
    ...    ───────────────────────────────────────────────────
    ...
    ...    This level of absenteeism is a matter of serious academic concern and may
    ...    result in the student being declared ineligible for end-term examinations
    ...    as per university regulations.
    ...
    ...    We strongly urge you to attend a PARENT-TEACHER MEETING at the earliest
    ...    convenience. Please contact the Head of Department or the administration
    ...    office to schedule a meeting:
    ...
    ...        📧 Contact: ${ADMIN_CONTACT}
    ...
    ...    Your cooperation in this matter is vital to ensure your ward's academic
    ...    continuity and future.
    ...
    ...    Regards,
    ...    ${INSTITUTION_NAME}
    ...    [This is an automated notification — please do not reply to this email]

    TRY
        Send Message
        ...    sender=${GMAIL_USER}
        ...    recipients=${parent_email}
        ...    subject=${subject}
        ...    body=${body}
        Log To Console    ✅ PTM invite sent → ${parent_email}
        Log    PTM invite sent: ${name} (${pct}%) → ${parent_email}    INFO
        RETURN    sent
    EXCEPT    AS    ${err}
        Log To Console    ❌ PTM invite FAILED → ${parent_email}: ${err}
        Log    PTM invite failed: ${name} → ${parent_email}: ${err}    ERROR
        RETURN    failed
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
