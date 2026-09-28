*** Settings ***
Documentation
...    ══════════════════════════════════════════════════════════════════
...    BOT 3 — Holiday Sync
...    University Automated Attendance & Alert System
...    ══════════════════════════════════════════════════════════════════
...
...    PURPOSE:
...      Reads a local academic_calendar.xlsx file and syncs all holiday
...      dates into the Django HolidayCalendar database table.
...
...      After sync, the Django attendance views check this table before
...      allowing absence marking — preventing incorrect attendance on
...      official holidays, exam days, and university events.
...
...    FLOW:
...      1. Read academic_calendar.xlsx using RPA.Excel.Files.
...      2. Parse every row: (Date, Holiday Name, Type).
...      3. Upsert each valid date into the core_holidaycalendar table.
...      4. Log a summary of how many new / updated holidays were synced.
...      5. Write an audit entry to RPABotLog.
...
...    EXPECTED EXCEL FORMAT:
...      Sheet Name: "Holidays" (or first sheet)
...      Columns:
...        A: Date         → YYYY-MM-DD format (or Excel Date cell)
...        B: Holiday Name → Free text, e.g. "Diwali"
...        C: Type         → National / University / Exam / Event / Other
...
...    ══════════════════════════════════════════════════════════════════

Library           DatabaseLibrary
Library           RPA.Excel.Files
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem


*** Variables ***
# ── Paths ─────────────────────────────────────────────────────────────────────
${DB_PATH}            ${CURDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}          sqlite3
${CALENDAR_PATH}      ${CURDIR}${/}..${/}academic_calendar.xlsx

# ── Excel Sheet Config ────────────────────────────────────────────────────────
${SHEET_NAME}         Holidays

# ── Bot Identity ──────────────────────────────────────────────────────────────
${BOT_NAME}           holiday_sync


*** Tasks ***
# ══════════════════════════════════════════════════════════════════
# MAIN TASK
# ══════════════════════════════════════════════════════════════════
Sync Academic Calendar Holidays
    [Documentation]
    ...    1. Verify that academic_calendar.xlsx exists.
    ...    2. Open the Excel file with RPA.Excel.Files.
    ...    3. Read all holiday rows from the 'Holidays' sheet.
    ...    4. For each row, upsert into the HolidayCalendar DB table.
    ...    5. Write an audit log entry.

    Print Banner    BOT 3 — HOLIDAY SYNC    STARTED

    # Guard: ensure the Excel file exists before proceeding
    File Should Exist    ${CALENDAR_PATH}
    ...    msg=academic_calendar.xlsx not found at ${CALENDAR_PATH}. Please place the file and re-run.

    # Step 1: Connect to SQLite DB
    Connect To Application Database

    # Step 2: Read Excel holidays
    ${holidays}=    Read Holiday Excel
    ${total}=       Get Length    ${holidays}
    Log To Console    📅 Read ${total} holiday row(s) from ${CALENDAR_PATH}

    # Step 3: Upsert into DB
    ${synced}=       Set Variable    ${0}
    ${skipped}=      Set Variable    ${0}
    ${errors}=       Set Variable    ${EMPTY}

    FOR    ${row}    IN    @{holidays}
        ${result}=    Upsert Holiday Row    ${row}
        IF    '${result}' == 'synced'
            ${synced}=    Evaluate    ${synced} + 1
        ELSE IF    '${result}' == 'skipped'
            ${skipped}=    Evaluate    ${skipped} + 1
        ELSE
            ${errors}=    Set Variable    ${errors} | Error: ${row}
        END
    END

    # Step 4: Audit log
    ${summary}=    Set Variable
    ...    Holiday Sync complete. Total rows: ${total}. Synced: ${synced}. Skipped/invalid: ${skipped}.
    Write Bot Log    ${summary}    ${synced}    ${errors}

    Print Banner    BOT 3 — HOLIDAY SYNC    FINISHED
    Log To Console    ✅ ${summary}

    [Teardown]    Disconnect From Database


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
Connect To Application Database
    Log To Console    🗄 Connecting to SQLite: ${DB_PATH}
    Connect To Database    ${DB_MODULE}    ${DB_PATH}
    Log To Console    ✅ DB connected.


# ══════════════════════════════════════════════════════════════════
# Read Holiday Excel
# Opens academic_calendar.xlsx and returns all rows from the
# 'Holidays' sheet as a list of dictionaries.
# Each dict has keys: Date, Holiday Name, Type
# ══════════════════════════════════════════════════════════════════
Read Holiday Excel
    [Documentation]
    ...    Uses RPA.Excel.Files to open the workbook and read rows.
    ...    Returns a list of row-dicts from the first sheet.
    Open Workbook    ${CALENDAR_PATH}

    # Try the named sheet first, fall back to first sheet
    TRY
        Set Active Worksheet    ${SHEET_NAME}
    EXCEPT
        Log To Console    ⚠️ Sheet '${SHEET_NAME}' not found — using first sheet.
        Set Active Worksheet By Index    0
    END

    ${table}=    Read Worksheet As Table    header=True
    Close Workbook
    RETURN    ${table}


# ══════════════════════════════════════════════════════════════════
# Upsert Holiday Row
# Inserts or replaces a single holiday into the DB.
# Returns: 'synced', 'skipped', or 'error'
# ══════════════════════════════════════════════════════════════════
Upsert Holiday Row
    [Documentation]    Upserts a single holiday row into core_holidaycalendar.
    [Arguments]    ${row}

    # Extract columns — handle both dict and list row formats
    TRY
        ${raw_date}=    Get From Dictionary    ${row}    Date
        ${name}=        Get From Dictionary    ${row}    Holiday Name
        ${h_type}=      Get From Dictionary    ${row}    Type
    EXCEPT
        Log To Console    ⚠️ Row format unexpected: ${row} — skipping.
        RETURN    skipped
    END

    # Validate: skip empty rows
    IF    '${raw_date}' == 'None' or '${name}' == 'None'
        Log To Console    ℹ️ Empty row encountered — skipping.
        RETURN    skipped
    END

    # Normalise date to YYYY-MM-DD string
    ${date_str}=    Normalise Date String    ${raw_date}
    IF    '${date_str}' == 'invalid'
        Log To Console    ⚠️ Invalid date '${raw_date}' — skipping row.
        RETURN    skipped
    END

    # Validate holiday type — default to 'University' if unknown
    ${valid_types}=    Create List    National    University    Exam    Event    Other
    ${clean_type}=    Set Variable If
    ...    '${h_type}' in ${valid_types}    ${h_type}    University

    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S

    TRY
        # INSERT OR REPLACE mirrors Django's HolidayCalendar.objects.update_or_create
        ${sql_ins}=    Catenate    SEPARATOR=\n
        ...    INSERT OR REPLACE INTO core_holidaycalendar
        ...        (date, name, holiday_type, synced_at, synced_by_bot)
        ...    VALUES
        ...        ('${date_str}', '${name}', '${clean_type}', '${now}', 1)
        Execute Sql String    ${sql_ins}
        Log To Console    ✅ Synced: ${date_str} — ${name} (${clean_type})
        RETURN    synced
    EXCEPT    AS    ${err}
        Log To Console    ❌ DB insert failed for ${date_str}: ${err}
        RETURN    error
    END


# ══════════════════════════════════════════════════════════════════
# Normalise Date String
# Converts Excel date values (float, datetime, or string) to
# YYYY-MM-DD string format for SQLite storage.
# ══════════════════════════════════════════════════════════════════
Normalise Date String
    [Documentation]    Returns a YYYY-MM-DD string or 'invalid' on failure.
    [Arguments]    ${raw_date}

    TRY
        # If already a string in YYYY-MM-DD, return as-is
        ${str_val}=    Convert To String    ${raw_date}
        ${stripped}=    Strip String    ${str_val}

        # Handle Excel numeric date (float like 45123.0)
        ${is_float}=    Run Keyword And Return Status
        ...    Should Match Regexp    ${stripped}    ^\\d+\\.\\d+$
        IF    ${is_float}
            # Convert Excel serial date to Python datetime via RF DateTime
            ${days}=    Evaluate    int(float('${stripped}'))
            # Excel epoch: 1899-12-30 (Windows) + days offset
            ${date_obj}=    Add Time To Date
            ...    1899-12-30 00:00:00
            ...    ${days} days
            ...    result_format=%Y-%m-%d
            RETURN    ${date_obj}
        END

        # Handle datetime objects (RPA.Excel sometimes returns these)
        ${has_space}=    Run Keyword And Return Status
        ...    Should Contain    ${stripped}    ${SPACE}
        IF    ${has_space}
            ${date_part}=    Fetch From Left    ${stripped}    ${SPACE}
            RETURN    ${date_part}
        END

        # Assume already in YYYY-MM-DD format
        ${valid}=    Run Keyword And Return Status
        ...    Should Match Regexp    ${stripped}    ^\\d{4}-\\d{2}-\\d{2}$
        IF    ${valid}
            RETURN    ${stripped}
        END

        RETURN    invalid
    EXCEPT
        RETURN    invalid
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
