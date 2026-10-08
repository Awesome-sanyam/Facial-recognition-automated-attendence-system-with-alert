*** Settings ***
Documentation
...    ══════════════════════════════════════════════════════════════════
...    BOT 5 — Nightly Database Backup & IT Health Check Report
...    University Automated Attendance & Alert System
...    ══════════════════════════════════════════════════════════════════
...
...    PURPOSE:
...      Nightly automated database backup bot. Runs on a schedule
...      (e.g., via cron or a Django management command trigger) to:
...
...      1. Create a timestamped SQLite database backup (.db file).
...      2. Compute an IT health check report:
...           • Total students, attendance records, leaves in DB
...           • Database file size
...           • Backup file size and location
...           • Timestamp of backup
...      3. Email the IT health report (plain text) to the admin.
...      4. Write an audit log to RPABotLog.
...
...    BACKUP APPROACH (SQLite):
...      SQLite has no native 'pg_dump' — instead we use Python's
...      'shutil.copy2()' for a safe binary copy of the .db file.
...      This is the standard backup strategy for SQLite in production.
...
...    NOTE: For PostgreSQL environments, this bot uses the
...      'pg_dump' shell command via OperatingSystem.Run.
...      Variables ${DB_TYPE} controls which path is taken.
...
...    ══════════════════════════════════════════════════════════════════

Library           DatabaseLibrary
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587


*** Variables ***
# ── Database Config ───────────────────────────────────────────────────────────
# DB_TYPE: 'sqlite' or 'postgres'
${DB_TYPE}            sqlite
${DB_PATH}            ${CURDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}          sqlite3

# ── PostgreSQL Config (used only if DB_TYPE=postgres) ─────────────────────────
${PG_HOST}            localhost
${PG_PORT}            5432
${PG_NAME}            attendance_db
${PG_USER}            postgres
${PG_PASS}            CONFIGURE_VIA_DASHBOARD

# ── Backup Config ─────────────────────────────────────────────────────────────
${BACKUP_DIR}         ${CURDIR}${/}..${/}backups

# ── Email Credentials ─────────────────────────────────────────────────────────
${GMAIL_USER}         CONFIGURE_VIA_DASHBOARD
${GMAIL_PASS}         CONFIGURE_VIA_DASHBOARD
${IT_ADMIN_EMAIL}     CONFIGURE_VIA_DASHBOARD

# ── Bot Identity ──────────────────────────────────────────────────────────────
${BOT_NAME}           db_backup


*** Tasks ***
# ══════════════════════════════════════════════════════════════════
# MAIN TASK
# ══════════════════════════════════════════════════════════════════
Nightly Database Backup And Health Report
    [Documentation]
    ...    1. Create a timestamped database backup.
    ...    2. Collect DB health metrics.
    ...    3. Email IT health report to admin.
    ...    4. Write audit log.

    Print Banner    BOT 5 — NIGHTLY DB BACKUP    STARTED

    # Step 1: Create backup
    ${backup_path}=    Create Database Backup

    # Step 2: Connect to DB and collect health metrics
    Connect To Application Database
    ${metrics}=    Collect Health Metrics    ${backup_path}

    # Step 3: Email IT health report
    IF    '${GMAIL_USER}' != 'CONFIGURE_VIA_DASHBOARD' and '${GMAIL_USER}' != '${EMPTY}'
        TRY
            Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
            Send IT Health Report    ${metrics}
            Close Connection
            Log To Console    ✅ IT health report emailed to: ${IT_ADMIN_EMAIL}
            ${summary}=    Set Variable
            ...    Nightly backup completed. File: ${backup_path}. DB stats collected and emailed to ${IT_ADMIN_EMAIL}.
        EXCEPT    AS    ${err}
            Log To Console    ⚠️ Could not email IT health report: ${err}
            ${summary}=    Set Variable
            ...    Nightly backup completed. File: ${backup_path}. DB stats collected. Email failed: ${err}.
        END
    ELSE
        Log To Console    ℹ️ Gmail credentials not configured — skipping email dispatch.
        ${summary}=    Set Variable
        ...    Nightly backup completed. File: ${backup_path}. DB stats collected. Email skipped (unconfigured).
    END

    # Step 4: Audit log
    Write Bot Log    ${summary}    ${metrics}[record_count]    ${EMPTY}

    Print Banner    BOT 5 — NIGHTLY DB BACKUP    FINISHED
    Log To Console    ✅ ${summary}

    [Teardown]    Disconnect From Database


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
Connect To Application Database
    Log To Console    🗄 Connecting to ${DB_TYPE} DB...
    IF    '${DB_TYPE}' == 'sqlite'
        Connect To Database    ${DB_MODULE}    ${DB_PATH}
    Execute Sql String    PRAGMA journal_mode=WAL
    Execute Sql String    PRAGMA busy_timeout=5000
    ELSE
        Connect To Database    psycopg2    ${PG_NAME}    ${PG_USER}    ${PG_PASS}    ${PG_HOST}    ${PG_PORT}
    END
    Log To Console    ✅ DB connected.


# ══════════════════════════════════════════════════════════════════
# Create Database Backup
# Creates a timestamped binary copy of the database.
# Returns the absolute path of the backup file.
# ══════════════════════════════════════════════════════════════════
Create Database Backup
    [Documentation]
    ...    For SQLite: uses shutil.copy2 for a safe, atomic binary copy.
    ...    For PostgreSQL: calls pg_dump via shell.
    ...    Returns the path to the backup file created.

    # Ensure backup directory exists
    Create Directory    ${BACKUP_DIR}

    ${timestamp}=    Get Current Date    result_format=%Y%m%d_%H%M%S

    IF    '${DB_TYPE}' == 'sqlite'
        ${backup_file}=    Set Variable    attendance_db_backup_${timestamp}.sqlite3
        ${backup_path}=    Join Path    ${BACKUP_DIR}    ${backup_file}

        Log To Console    💾 Creating SQLite backup: ${backup_path}

        # Use native OperatingSystem keyword for safe binary copy
        Copy File    ${DB_PATH}    ${backup_path}
        File Should Exist    ${backup_path}    msg=SQLite backup file was not created.
        Log To Console    ✅ SQLite backup created: ${backup_path}


    ELSE
        # PostgreSQL: pg_dump to a .sql file
        ${backup_file}=    Set Variable    attendance_db_backup_${timestamp}.sql
        ${backup_path}=    Join Path    ${BACKUP_DIR}    ${backup_file}

        Log To Console    💾 Creating PostgreSQL pg_dump: ${backup_path}

        ${pg_result}=    Run
        ...    pg_dump -h ${PG_HOST} -p ${PG_PORT} -U ${PG_USER} -F p -f "${backup_path}" ${PG_NAME}

        # pg_dump returns empty string on success
        File Should Exist    ${backup_path}
        ...    msg=pg_dump failed. Output: ${pg_result}

        Log To Console    ✅ PostgreSQL dump created: ${backup_path}
    END

    RETURN    ${backup_path}


# ══════════════════════════════════════════════════════════════════
# Collect Health Metrics
# Queries DB for key statistics and computes backup file size.
# Returns a dictionary of metrics for the IT report.
# ══════════════════════════════════════════════════════════════════
Collect Health Metrics
    [Documentation]    Gathers DB statistics and file size info.
    [Arguments]    ${backup_path}

    Log To Console    📊 Collecting IT health metrics...

    # Count total students
    ${students_result}=    Query
    ...    SELECT COUNT(*) FROM core_student
    ${student_count}=    Set Variable    ${students_result[0][0]}

    # Count total attendance records
    ${att_result}=    Query
    ...    SELECT COUNT(*) FROM core_attendancerecord
    ${att_count}=    Set Variable    ${att_result[0][0]}

    # Count total leave applications
    ${leave_result}=    Query
    ...    SELECT COUNT(*) FROM core_leaveapplication
    ${leave_count}=    Set Variable    ${leave_result[0][0]}

    # Count pending leaves
    ${pending_result}=    Query
    ...    SELECT COUNT(*) FROM core_leaveapplication WHERE status = 'Pending'
    ${pending_count}=    Set Variable    ${pending_result[0][0]}

    # Count students below 75%
    ${sql_low}=    Catenate    SEPARATOR=\n
    ...    SELECT COUNT(*) FROM (
    ...        SELECT s.id FROM core_student s
    ...        LEFT JOIN (
    ...            SELECT student_id, COUNT(*) as cnt FROM core_attendancerecord
    ...            WHERE status != 'Excused' GROUP BY student_id
    ...        ) c ON c.student_id = s.id
    ...        LEFT JOIN (
    ...            SELECT student_id, COUNT(*) as cnt FROM core_attendancerecord
    ...            WHERE status = 'Present' GROUP BY student_id
    ...        ) p ON p.student_id = s.id
    ...        WHERE c.cnt > 0 AND (CAST(COALESCE(p.cnt,0) AS REAL)/CAST(c.cnt AS REAL)*100) < 75
    ...    )
    ${low_att_result}=    Query    ${sql_low}
    ${low_count}=    Set Variable    ${low_att_result[0][0]}

    # Get backup file size (in KB)
    ${backup_size_bytes}=    Get File Size    ${backup_path}
    ${backup_size_kb}=    Evaluate    round(${backup_size_bytes} / 1024, 2)

    # Get main DB file size (in KB)
    ${db_size_bytes}=    Get File Size    ${DB_PATH}
    ${db_size_kb}=    Evaluate    round(${db_size_bytes} / 1024, 2)


    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S

    # Build and return metrics dictionary
    ${metrics}=    Create Dictionary
    ...    timestamp=${now}
    ...    student_count=${student_count}
    ...    att_count=${att_count}
    ...    leave_count=${leave_count}
    ...    pending_count=${pending_count}
    ...    low_att_count=${low_count}
    ...    backup_path=${backup_path}
    ...    backup_size_kb=${backup_size_kb}
    ...    db_size_kb=${db_size_kb}
    ...    record_count=${att_count}

    Log To Console    📊 Metrics collected: ${student_count} students, ${att_count} records.
    RETURN    ${metrics}


# ══════════════════════════════════════════════════════════════════
# Send IT Health Report
# Emails a plain text IT health report to the admin.
# ══════════════════════════════════════════════════════════════════
Send IT Health Report
    [Documentation]    Sends the nightly IT health report email.
    [Arguments]    ${metrics}

    ${subject}=    Set Variable
    ...    [Nightly Backup] Attendance System IT Health Report — ${metrics}[timestamp]

    ${body}=    Catenate    SEPARATOR=\n
    ...    ══════════════════════════════════════════════════════════════
    ...    NIGHTLY IT HEALTH CHECK REPORT
    ...    University Attendance & Alert System
    ...    Generated: ${metrics}[timestamp]
    ...    ══════════════════════════════════════════════════════════════
    ...
    ...    DATABASE STATISTICS
    ...    ─────────────────────────────────────────────
    ...    Total Students             : ${metrics}[student_count]
    ...    Total Attendance Records   : ${metrics}[att_count]
    ...    Total Leave Applications   : ${metrics}[leave_count]
    ...    Pending Leave Applications : ${metrics}[pending_count]
    ...    Students Below 75%         : ${metrics}[low_att_count]
    ...
    ...    BACKUP DETAILS
    ...    ─────────────────────────────────────────────
    ...    Backup File  : ${metrics}[backup_path]
    ...    Backup Size  : ${metrics}[backup_size_kb] KB
    ...    Source DB    : ${DB_PATH}
    ...    Source Size  : ${metrics}[db_size_kb] KB
    ...    Status       : ✅ BACKUP SUCCESSFUL
    ...
    ...    ══════════════════════════════════════════════════════════════
    ...    This report was generated automatically by the RPA Bot.
    ...    No action is required if status shows SUCCESSFUL.
    ...    Contact the system administrator if backup failed.
    ...    ══════════════════════════════════════════════════════════════

    Log To Console    📧 Sending IT Health Report to: ${IT_ADMIN_EMAIL}

    TRY
        Send Message
        ...    sender=${GMAIL_USER}
        ...    recipients=${IT_ADMIN_EMAIL}
        ...    subject=${subject}
        ...    body=${body}
        Log To Console    ✅ IT Health Report emailed to: ${IT_ADMIN_EMAIL}
    EXCEPT    AS    ${err}
        Log To Console    ❌ IT Health Report email failed: ${err}
        Log    IT Health email failed: ${err}    ERROR
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

        # Granular log for Live Automation Hub
        ${act_sql}=    Catenate    SEPARATOR=\n
        ...    INSERT INTO core_botactivitylog
        ...        (bot_name, action, target, timestamp, status, detail)
        ...    VALUES
        ...        ('${BOT_NAME}', '${summary}', 'db.sqlite3', '${now}', '${status}', 'Nightly backup via Robot Framework')
        Execute Sql String    ${act_sql}
        Log To Console    📝 Audit log written.
    EXCEPT    AS    ${err}
        Log To Console    ⚠️ Could not write audit log: ${err}
    END


Print Banner
    [Arguments]    ${title}    ${state}
    Log To Console    \n======================================================
    Log To Console    [${title} -- ${state}]
    Log To Console    ======================================================
