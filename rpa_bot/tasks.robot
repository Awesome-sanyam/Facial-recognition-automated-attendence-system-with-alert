*** Settings ***
Documentation     University Attendance RPA Bot
...               Flow: Faculty Web Portal → Dashboard → Read Student Data → Send Alerts
...               This bot navigates the ACTUAL faculty web pages (NOT Django Admin).
Library           SeleniumLibrary
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587
Library           SmsLibrary.py
Library           String
Library           Collections

# ── Global Selenium Speed ─────────────────────────────────────────────────────
# Set to 0.1s for a very fast (but still visual) pace.
Suite Setup       Set Selenium Speed    0.1s

*** Variables ***
# ── Faculty Web Portal (not Django Admin) ─────────────────────────────────────
${BASE_URL}       http://127.0.0.1:8000
${LOGIN_URL}      http://127.0.0.1:8000/faculty/login/
${DASHBOARD_URL}  http://127.0.0.1:8000/faculty/dashboard/?tab=students

# ── Faculty Credentials ────────────────────────────────────────────────────────
${FACULTY_USER}   admin
${FACULTY_PASS}   admin

# ── Alert Threshold ───────────────────────────────────────────────────────────
${THRESHOLD}      ${75.0}

# ── Gmail credentials ─ injected by save_alert_config via Faculty Dashboard ───
${GMAIL_USER}     CONFIGURE_VIA_FACULTY_DASHBOARD
${GMAIL_PASS}     CONFIGURE_VIA_FACULTY_DASHBOARD

# ── Twilio credentials ─ injected by save_alert_config via Faculty Dashboard ──
${TWILIO_SID}     CONFIGURE_VIA_FACULTY_DASHBOARD
${TWILIO_TOKEN}     CONFIGURE_VIA_FACULTY_DASHBOARD
${TWILIO_FROM}     CONFIGURE_VIA_FACULTY_DASHBOARD
${SMS_ENABLED}     False


*** Tasks ***
Process Weekly Attendance Alerts
    [Documentation]    Full RPA flow through the faculty web portal:
    ...    1. Open Faculty Login page in Chrome
    ...    2. Login with faculty credentials
    ...    3. Navigate to Student Attendance Roster on the Dashboard
    ...    4. Scrape every student's name, email, phone and attendance %
    ...    5. For each student below the threshold, dispatch Email + SMS alert
    Open Faculty Web Portal
    Login To Faculty Portal
    Navigate To Student Attendance Roster
    Authorize Email Server
    Authorize SMS Server
    Audit And Alert Low Attendance Students
    Log    ✅ Weekly attendance audit completed via Faculty Web Portal!
    [Teardown]    Run Keywords
    ...    Close Browser
    ...    AND    Close Connection


*** Keywords ***

Highlight Element
    [Documentation]    Draws a bright orange border around the target element
    ...                so the user can clearly see which element the bot is about to interact with.
    [Arguments]    ${locator}
    ${element}=    Get WebElement    ${locator}
    Execute Javascript
    ...    arguments[0].style.outline = '3px solid orange';
    ...    arguments[0].style.outlineOffset = '2px';
    ...    arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
    ...    ARGUMENTS    ${element}
    Sleep    0.3s
    Execute Javascript
    ...    arguments[0].style.outline = '';
    ...    arguments[0].style.outlineOffset = '';
    ...    ARGUMENTS    ${element}

Open Faculty Web Portal
    [Documentation]    Launch Chrome and open the Faculty Login page.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 1 ▶ Opening Faculty Web Portal ║
    Log To Console    ╚══════════════════════════════════════════════════════╝
    Open Browser    ${LOGIN_URL}    chrome
    Maximize Browser Window
    Sleep    0.5s
    Wait Until Page Contains    Faculty Login    timeout=15s
    Log To Console    ✅ Faculty Login page loaded: ${LOGIN_URL}

Login To Faculty Portal
    [Documentation]    Fill in username + password on the faculty login form and submit.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 2 ▶ Logging In as Faculty ║
    Log To Console    ╚══════════════════════════════════════════════════════╝

    # Highlight and fill username
    Highlight Element    css:input[name="username"]
    Log To Console    🖊 Typing username: ${FACULTY_USER}
    Input Text        css:input[name="username"]    ${FACULTY_USER}
    Sleep    0.4s

    # Highlight and fill password
    Highlight Element    css:input[name="password"]
    Log To Console    🖊 Typing password...
    Input Password    css:input[name="password"]    ${FACULTY_PASS}
    Sleep    0.4s

    # Highlight submit button, then click
    Highlight Element    css:button[type="submit"]
    Log To Console    🖱 Clicking LOGIN button
    Sleep    0.2s
    Click Button      css:button[type="submit"]

    # Wait for dashboard to load
    Log To Console    ⏳ Waiting for dashboard to load...
    Wait Until Page Contains    Student Attendance Roster    timeout=20s
    Sleep    0.5s
    Log To Console    ✅ Logged into Faculty Portal as ${FACULTY_USER}

Navigate To Student Attendance Roster
    [Documentation]    Go to the Students tab on the faculty dashboard.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 3 ▶ Navigating to Student Attendance Roster ║
    Log To Console    ╚══════════════════════════════════════════════════════╝
    Log To Console    🌐 Navigating to: ${DASHBOARD_URL}
    Go To    ${DASHBOARD_URL}
    Wait Until Page Contains    Student Attendance Roster    timeout=15s
    Sleep    0.8s
    Log To Console    ✅ Student Attendance Roster loaded

Authorize Email Server
    [Documentation]    Connect to Gmail SMTP using credentials from the dashboard config.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 4 ▶ Authorising Gmail SMTP Server ║
    Log To Console    ╚══════════════════════════════════════════════════════╝
    Log To Console    📧 Connecting to Gmail SMTP as: ${GMAIL_USER}
    Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
    Sleep    0.2s
    Log To Console    ✅ Gmail SMTP authorised

Authorize SMS Server
    [Documentation]    Initialise Twilio client using credentials from the dashboard config.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 5 ▶ Authorising Twilio SMS Client ║
    Log To Console    ╚══════════════════════════════════════════════════════╝
    Log To Console    📱 Initialising Twilio (SMS_ENABLED=${SMS_ENABLED})
    Authorize SMS    account_sid=${TWILIO_SID}    auth_token=${TWILIO_TOKEN}    from_number=${TWILIO_FROM}
    Sleep    0.2s
    Log To Console    ✅ Twilio SMS client authorised

Audit And Alert Low Attendance Students
    [Documentation]
    ...    Reads every student row from the Faculty Dashboard student table.
    ...    Each <tr class="student-row"> has data attributes:
    ...       data-student-name, data-parent-email, data-parent-phone, data-attendance
    ...    For each student below the threshold, sends Email + SMS.
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 6 ▶ Auditing Student Attendance Records ║
    Log To Console    ╚══════════════════════════════════════════════════════╝

    # Count how many student rows the dashboard rendered
    ${row_count}=    Get Element Count    css:tr.student-row
    Log To Console    📋 Found ${row_count} student(s) in the Attendance Roster
    Log To Console    📊 Alert threshold: ${THRESHOLD}%
    Sleep    0.5s

    FOR    ${i}    IN RANGE    1    ${row_count} + 1
     Log To Console    \n──────────────────────────────────────────────────────
     Log To Console    🔍 Processing student ${i} of ${row_count}...

        # Highlight the current row so it's visible on screen
        Highlight Element    xpath:(//tr[contains(@class,'student-row')])[${i}]
        Sleep    0.2s

        # Read from data-* attributes — reliable regardless of column order
        ${name}=     Get Element Attribute
        ...    xpath:(//tr[contains(@class,'student-row')])[${i}]
        ...    data-student-name
        ${email}=    Get Element Attribute
        ...    xpath:(//tr[contains(@class,'student-row')])[${i}]
        ...    data-parent-email
        ${phone}=    Get Element Attribute
        ...    xpath:(//tr[contains(@class,'student-row')])[${i}]
        ...    data-parent-phone
        ${att_str}=  Get Element Attribute
        ...    xpath:(//tr[contains(@class,'student-row')])[${i}]
        ...    data-attendance

        ${att_val}=  Convert To Number    ${att_str}
     Log To Console    👤 Student : ${name}
     Log To Console    📧 Email : ${email}
     Log To Console    📱 Phone : ${phone}
     Log To Console    📈 Attendance: ${att_val}% (threshold: ${THRESHOLD}%)
        Sleep    0.4s

        IF    ${att_val} < ${THRESHOLD}
     Log To Console    ⚠️ LOW ATTENDANCE — sending alert!
            Log    LOW ATTENDANCE: ${name} | ${att_val}% (below ${THRESHOLD}%) | Email: ${email} | Phone: ${phone}    INFO
            Send Warning Email    ${email}    ${name}    ${att_val}
            Sleep    0.2s
            IF    '${SMS_ENABLED}' == 'True'
                Send Warning SMS    ${phone}    ${name}    ${att_val}
                Sleep    0.2s
            END
        ELSE
     Log To Console    ✅ COMPLIANT — ${name} at ${att_val}% — no action needed
            Log    COMPLIANT: ${name} | ${att_val}% | No action needed    INFO
        END
        Sleep    0.2s
    END
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║ STEP 6 COMPLETE ▶ All students processed ║
    Log To Console    ╚══════════════════════════════════════════════════════╝

Send Warning Email
    [Arguments]    ${recipient_email}    ${student_name}    ${attendance_pct}
    Log To Console    ✉ Preparing email to: ${recipient_email}
    ${subject}=    Set Variable
    ...    URGENT: Low Attendance Warning — ${student_name}
    ${body}=       Set Variable
    ...    Dear Parent/Guardian,\n\nThis is an automated alert from the University Attendance System.\n\nStudent: ${student_name}\nCurrent Attendance: ${attendance_pct}%\nRequired Minimum: ${THRESHOLD}%\n\nThe attendance has dropped below the mandatory threshold.\nPlease submit a leave application or contact the administration immediately.\n\nThis message was sent automatically by the Faculty RPA Bot.\n\nRegards,\nUniversity Attendance System
    Send Message
    ...    sender=${GMAIL_USER}
    ...    recipients=${recipient_email}
    ...    subject=${subject}
    ...    body=${body}
    Log To Console    ✅ Email dispatched → ${recipient_email}

Send Warning SMS
    [Arguments]    ${recipient_phone}    ${student_name}    ${attendance_pct}
    ${body}=    Set Variable
    ...    URGENT: ${student_name} has ${attendance_pct}% attendance (below ${THRESHOLD}% threshold). Contact administration immediately.
    # Ensure E.164 format — add +91 prefix for Indian numbers without country code
    ${clean_phone}=       Remove String    ${recipient_phone}    ${SPACE}
    ${formatted_phone}=   Set Variable If
    ...    '${clean_phone}'.startswith('+')    ${clean_phone}
    ...    '+91${clean_phone}'
    # TRY/EXCEPT: gracefully handle Twilio trial-account unverified-number errors
    # so the bot continues to the next student instead of failing the whole task.
    TRY
        Send Sms    to_number=${formatted_phone}    body=${body}
        Log    SMS dispatched to ${formatted_phone}    INFO
    EXCEPT    message=*unverified*    type=GLOB
        Log    WARN: SMS to ${formatted_phone} skipped — number not verified in Twilio trial account. Register it at twilio.com/user/account/phone-numbers/verified    WARN
    EXCEPT
        Log    WARN: SMS to ${formatted_phone} failed — check Twilio credentials    WARN
    END