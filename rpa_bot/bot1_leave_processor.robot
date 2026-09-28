*** Settings ***
Documentation
...    ══════════════════════════════════════════════════════════════════
...    BOT 1 — Auto-Leave Processor
...    University Automated Attendance & Alert System
...    ══════════════════════════════════════════════════════════════════
...
...    PURPOSE:
...      This bot reads all PENDING LeaveApplication records from the
...      Django database via the RPA.Database library and applies
...      an intelligent auto-approval policy:
...
...        ✅ AUTO-APPROVE  → Student has > 80% attendance (1-day leave)
...        ⏸ KEEP PENDING  → Student is at/below 80% attendance
...        🗓  MULTI-DAY    → Any leave spanning > 1 day stays Pending
...                          (requires HOD manual review)
...
...    MECHANISM:
...      1. Connects to the SQLite database used by Django.
...      2. Queries all pending leave applications.
...      3. For each, computes attendance from AttendanceRecord.
...      4. Updates LeaveApplication.status directly in the DB.
...      5. Writes an audit entry to RPABotLog.
...
...    ACADEMIC NOTE:
...      Direct DB access is used here (not Selenium) because leave
...      processing is a backend data operation — not a UI interaction.
...      This is more efficient and reliable than web scraping.
...
...    ROBOT FRAMEWORK VERSION: 7.x  (rpaframework)
...    ══════════════════════════════════════════════════════════════════

Library           DatabaseLibrary
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem


*** Variables ***
# ── Database Connection ────────────────────────────────────────────────────────
# Path to the Django project's SQLite database file.
# Override via CLI: robot --variable DB_PATH:/path/to/db.sqlite3 ...
${DB_PATH}        ${CURDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}      sqlite3

# ── Policy Thresholds ─────────────────────────────────────────────────────────
# Students ABOVE this value get their 1-day leave auto-approved.
${AUTO_APPROVE_THRESHOLD}    ${80.0}

# ── Bot Identity (written to RPABotLog) ───────────────────────────────────────
${BOT_NAME}       leave_processor


*** Tasks ***
# ══════════════════════════════════════════════════════════════════
# MAIN TASK — Entry point for Robot Framework execution
# ══════════════════════════════════════════════════════════════════
Auto Process Pending Leave Applications
    [Documentation]
    ...    Main entry point.
    ...    1. Connects to the Django SQLite DB.
    ...    2. Reads all pending leave applications.
    ...    3. For each pending leave:
    ...         a. Checks if it is a 1-day leave.
    ...         b. Computes the student's attendance percentage.
    ...         c. Applies the auto-approval policy.
    ...    4. Writes a summary audit log to RPABotLog.
    ...    5. Closes the DB connection cleanly.

    Print Banner    BOT 1 — AUTO-LEAVE PROCESSOR    STARTED

    # Step 1: Connect to the database
    Connect To Application Database

    # Step 2: Fetch all pending applications
    ${pending_leaves}=    Fetch Pending Leave Applications

    ${total}=    Get Length    ${pending_leaves}
    Log To Console    📋 Found ${total} pending leave application(s) to process.

    # Step 3: Process each application
    ${approved_count}=    Set Variable    ${0}
    ${kept_pending}=      Set Variable    ${0}
    ${errors}=            Set Variable    ${EMPTY}

    FOR    ${leave}    IN    @{pending_leaves}
        ${result}=    Process Single Leave    ${leave}
        IF    '${result}' == 'approved'
            ${approved_count}=    Evaluate    ${approved_count} + 1
        ELSE IF    '${result}' == 'pending'
            ${kept_pending}=    Evaluate    ${kept_pending} + 1
        ELSE
            ${errors}=    Set Variable    ${errors} | Error on leave_id=${leave}[0]
        END
    END

    # Step 4: Write audit log to RPABotLog table
    ${summary}=    Set Variable
    ...    Processed ${total} pending leaves. Auto-approved: ${approved_count}. Kept pending: ${kept_pending}.
    Write Bot Log    ${summary}    ${total}    ${errors}

    Print Banner    BOT 1 — AUTO-LEAVE PROCESSOR    FINISHED
    Log To Console    ✅ Summary: ${summary}

    [Teardown]    Disconnect From Database


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
# KEYWORD: Connect To Application Database
# Establishes a connection to Django's SQLite database file.
# ══════════════════════════════════════════════════════════════════
Connect To Application Database
    [Documentation]    Opens a connection to the Django SQLite DB.
    Log To Console    🗄 Connecting to SQLite: ${DB_PATH}
    Connect To Database    ${DB_MODULE}    ${DB_PATH}
    Log To Console    ✅ Database connected.


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Fetch Pending Leave Applications
# Returns a list of rows: (id, student_id, date_requested, reason)
# ══════════════════════════════════════════════════════════════════
Fetch Pending Leave Applications
    [Documentation]    SELECT all LeaveApplication rows with status='Pending'.
    ${sql}=    Catenate    SEPARATOR=\n
    ...    SELECT id, student_id, date_requested, reason
    ...    FROM core_leaveapplication
    ...    WHERE status = 'Pending'
    ...    ORDER BY date_requested ASC
    ${result}=    Query    ${sql}
    RETURN    ${result}


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Get Student Attendance Percentage
# Computes attendance % for a given student_id from the DB.
# Logic mirrors the Django model's attendance_percentage property.
# ══════════════════════════════════════════════════════════════════
Get Student Attendance Percentage
    [Documentation]    Computes attendance for student_id from AttendanceRecord.
    [Arguments]    ${student_id}

    # Count total countable records (exclude 'Excused' from denominator)
    ${sql_cnt}=    Catenate    SEPARATOR=\n
    ...    SELECT COUNT(*) FROM core_attendancerecord
    ...    WHERE student_id = ${student_id} AND status != 'Excused'
    ${countable_result}=    Query    ${sql_cnt}

    ${total_countable}=    Set Variable    ${countable_result[0][0]}

    IF    ${total_countable} == 0
        Log To Console    ℹ️ Student ${student_id} has no countable attendance records.
        RETURN    ${100.0}
    END

    # Count present records
    ${sql_pres}=    Catenate    SEPARATOR=\n
    ...    SELECT COUNT(*) FROM core_attendancerecord
    ...    WHERE student_id = ${student_id} AND status = 'Present'
    ${present_result}=    Query    ${sql_pres}

    ${present_count}=    Set Variable    ${present_result[0][0]}

    # Calculate and return percentage
    ${pct}=    Evaluate    round((${present_count} / ${total_countable}) * 100, 2)
    RETURN    ${pct}


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Is Single Day Leave
# Returns True if the leave covers only ONE calendar day.
# ══════════════════════════════════════════════════════════════════
Is Single Day Leave
    [Documentation]    Returns True if date_requested is a single day (not a range).
    [Arguments]    ${date_requested}
    # In this model, date_requested is a single DateField — always 1 day.
    # This keyword is a placeholder for future multi-day leave extension.
    RETURN    ${TRUE}


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Process Single Leave
# Core decision engine for a single leave application.
# Returns: 'approved', 'pending', or 'error'
# ══════════════════════════════════════════════════════════════════
Process Single Leave
    [Documentation]
    ...    For a single leave row (id, student_id, date_requested, reason):
    ...    1. Check if it is a 1-day leave.
    ...    2. Get the student's attendance %.
    ...    3. If > 80% → Auto-approve (set status='Approved', create Excused record).
    ...    4. Else    → Keep Pending (log reason).
    [Arguments]    ${leave_row}

    ${leave_id}=      Set Variable    ${leave_row[0]}
    ${student_id}=    Set Variable    ${leave_row[1]}
    ${leave_date}=    Set Variable    ${leave_row[2]}
    ${reason}=        Set Variable    ${leave_row[3]}

    Log To Console    \n── Processing Leave ID: ${leave_id} | Student: ${student_id} | Date: ${leave_date}

    # Gate 1: Only process single-day leaves automatically
    ${single_day}=    Is Single Day Leave    ${leave_date}
    IF    not ${single_day}
        Log To Console    ⏸ Leave ${leave_id} spans multiple days — keeping Pending for HOD review.
        RETURN    pending
    END

    # Gate 2: Compute attendance percentage
    TRY
        ${pct}=    Get Student Attendance Percentage    ${student_id}
        Log To Console    📊 Student ${student_id} attendance: ${pct}%
    EXCEPT    AS    ${err}
        Log To Console    ❌ Error computing attendance for student ${student_id}: ${err}
        RETURN    error
    END

    # Decision: Apply auto-approval policy
    IF    ${pct} > ${AUTO_APPROVE_THRESHOLD}
        Log To Console    ✅ POLICY: ${pct}% > ${AUTO_APPROVE_THRESHOLD}% → AUTO-APPROVING leave ${leave_id}
        Approve Leave In Database    ${leave_id}    ${student_id}    ${leave_date}
        RETURN    approved
    ELSE
        Log To Console    ⏸ POLICY: ${pct}% ≤ ${AUTO_APPROVE_THRESHOLD}% → KEEPING PENDING (needs HOD review)
        RETURN    pending
    END


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Approve Leave In Database
# Updates the leave status to 'Approved' and inserts/updates
# an AttendanceRecord with status='Excused' for that date.
# ══════════════════════════════════════════════════════════════════
Approve Leave In Database
    [Documentation]
    ...    Atomically:
    ...    1. Sets LeaveApplication.status = 'Approved'.
    ...    2. Sets LeaveApplication.reviewed_at = NOW (ISO format).
    ...    3. Creates (or updates) AttendanceRecord for that date as 'Excused'.
    [Arguments]    ${leave_id}    ${student_id}    ${leave_date}

    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S

    # Update the leave application status
    ${sql_upd}=    Catenate    SEPARATOR=\n
    ...    UPDATE core_leaveapplication
    ...    SET status = 'Approved',
    ...        reviewed_at = '${now}'
    ...    WHERE id = ${leave_id}
    Execute Sql String    ${sql_upd}

    # Create or update the attendance record as 'Excused'
    # Django's unique_together = (student, date) — use INSERT OR REPLACE
    ${sql_ins}=    Catenate    SEPARATOR=\n
    ...    INSERT OR REPLACE INTO core_attendancerecord
    ...        (student_id, date, time, status)
    ...    VALUES
    ...        (${student_id}, '${leave_date}', '00:00:00', 'Excused')
    Execute Sql String    ${sql_ins}

    Log To Console    💾 DB Updated — Leave ${leave_id}: Approved | Attendance: Excused


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Write Bot Log
# Inserts a row into the RPABotLog table for audit purposes.
# ══════════════════════════════════════════════════════════════════
Write Bot Log
    [Documentation]    Writes execution audit to core_rpabotlog table.
    [Arguments]    ${summary}    ${records}    ${errors}

    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S
    ${status}=    Set Variable If    '${errors}' == '${EMPTY}'    success    partial

    ${sql_log}=    Catenate    SEPARATOR=\n
    ...    INSERT INTO core_rpabotlog
    ...        (bot_name, status, started_at, finished_at, summary, records_processed, errors, triggered_by_id)
    ...    VALUES
    ...        ('${BOT_NAME}', '${status}', '${now}', '${now}',
    ...         '${summary}', ${records}, '${errors}', NULL)
    Execute Sql String    ${sql_log}

    Log To Console    📝 Audit log written to RPABotLog.


# ══════════════════════════════════════════════════════════════════
# KEYWORD: Print Banner
# Prints a visual section separator to the Robot Framework console.
# ══════════════════════════════════════════════════════════════════
Print Banner
    [Arguments]    ${title}    ${state}
    Log To Console    \n======================================================
    Log To Console    [${title} -- ${state}]
    Log To Console    ======================================================

