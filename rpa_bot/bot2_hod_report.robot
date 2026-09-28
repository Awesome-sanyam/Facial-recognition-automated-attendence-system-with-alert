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

Library           RPA.Database
Library           Collections
Library           DateTime
Library           String
Library           OperatingSystem
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587


*** Variables ***
# ── Database ──────────────────────────────────────────────────────────────────
${DB_PATH}        ${EXECDIR}${/}..${/}web_app${/}db.sqlite3
${DB_MODULE}      sqlite3

# ── Report Config ─────────────────────────────────────────────────────────────
${HOD_THRESHOLD}          ${75.0}
${REPORT_OUTPUT_DIR}      ${EXECDIR}${/}reports

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
    Connect To Database

    # ── Step 2 & 3: Fetch low-attendance students ───────────────────
    ${low_students}=    Fetch Students Below Threshold

    ${count}=    Get Length    ${low_students}
    Log To Console    📋 Found ${count} student(s) below ${HOD_THRESHOLD}% threshold.

    IF    ${count} == 0
        Log To Console    ✅ All students meet the attendance threshold — no PDF needed.
        Write Bot Log    No students below threshold. Report not generated.    ${0}    ${EMPTY}
        RETURN
    END

    # ── Step 4: Generate PDF ────────────────────────────────────────
    ${report_path}=    Generate PDF Report    ${low_students}    ${count}

    # ── Step 5: Email PDF to Dean ───────────────────────────────────
    Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
    Send HOD Report Email    ${report_path}    ${count}

    # ── Step 6: Audit log ───────────────────────────────────────────
    ${summary}=    Set Variable
    ...    HOD Report generated with ${count} at-risk student(s). Emailed to ${DEAN_EMAIL}.
    Write Bot Log    ${summary}    ${count}    ${EMPTY}

    Print Banner    BOT 2 — HOD PDF REPORT    FINISHED
    Log To Console    ✅ ${summary}

    [Teardown]    Run Keywords
    ...    Disconnect From Database
    ...    AND    Close Connection


*** Keywords ***
# ══════════════════════════════════════════════════════════════════
Connect To Database
    Log To Console    🗄  Connecting to SQLite: ${DB_PATH}
    Connect To Database Using Custom Params
    ...    ${DB_MODULE}
    ...    database="${DB_PATH}"
    Log To Console    ✅ Database connected.


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

    ${result}=    Query
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

    RETURN    ${result}


# ══════════════════════════════════════════════════════════════════
# Generate a professional PDF report using ReportLab.
# Returns the absolute file path of the generated PDF.
# ══════════════════════════════════════════════════════════════════
Generate PDF Report
    [Documentation]
    ...    Creates a formatted PDF at ${REPORT_OUTPUT_DIR}/HOD_Report_<date>.pdf
    ...    Uses ReportLab SimpleDocTemplate with a styled Table.
    [Arguments]    ${students}    ${count}

    # Ensure the output directory exists
    Create Directory    ${REPORT_OUTPUT_DIR}

    ${today}=    Get Current Date    result_format=%Y-%m-%d
    ${report_filename}=    Set Variable    HOD_Report_${today}.pdf
    ${report_path}=    Join Path    ${REPORT_OUTPUT_DIR}    ${report_filename}

    # Call Python keyword to build the PDF using ReportLab
    Build PDF With ReportLab    ${report_path}    ${students}    ${count}    ${today}

    Log To Console    📄 PDF Report generated: ${report_path}
    RETURN    ${report_path}


Build PDF With ReportLab
    [Documentation]
    ...    Pure Python keyword that uses reportlab to build the PDF.
    ...    This is called from the RF keyword above.
    [Arguments]    ${output_path}    ${students}    ${count}    ${report_date}

    # Using Evaluate to run Python inline (RF 7 compatible approach)
    ${py_code}=    Catenate    SEPARATOR=\n
    ...    from reportlab.lib.pagesizes import A4
    ...    from reportlab.lib import colors
    ...    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    ...    from reportlab.lib.units import cm
    ...    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    ...    from reportlab.lib.enums import TA_CENTER
    ...    doc = SimpleDocTemplate(r'${output_path}', pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm)
    ...    styles = getSampleStyleSheet()
    ...    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, textColor=colors.HexColor('#1a1a2e'))
    ...    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, textColor=colors.grey)
    ...    elements = []
    ...    elements.append(Paragraph('Monthly Attendance Risk Report', title_style))
    ...    elements.append(Paragraph(f'University Attendance System | Report Date: ${report_date}', sub_style))
    ...    elements.append(Paragraph(f'Students Below 75% Attendance Threshold | Total At-Risk: ${count}', sub_style))
    ...    elements.append(Spacer(1, 0.5*cm))
    ...    headers = ['#', 'Student Name', 'Enrollment No.', 'Department', 'Year', 'Parent Email', 'Attendance %']
    ...    table_data = [headers]
    ...    students_list = ${students}
    ...    for idx, row in enumerate(students_list, 1):
    ...        name, enr, dept, year, parent_email, pct = row
    ...        risk = 'CRITICAL' if pct < 50 else 'LOW'
    ...        table_data.append([str(idx), str(name), str(enr), str(dept) or 'N/A', f'Year {year}', str(parent_email), f'{pct}%'])
    ...    col_widths = [1*cm, 4*cm, 3.5*cm, 3.5*cm, 1.8*cm, 5*cm, 2.5*cm]
    ...    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    ...    t.setStyle(TableStyle([
    ...        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a1a2e')),
    ...        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
    ...        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ...        ('FONTSIZE', (0,0), (-1,0), 9),
    ...        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ...        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ...        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
    ...        ('FONTSIZE', (0,1), (-1,-1), 8),
    ...        ('GRID', (0,0), (-1,-1), 0.3, colors.lightgrey),
    ...        ('TOPPADDING', (0,0), (-1,-1), 6),
    ...        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ...    ]))
    ...    elements.append(t)
    ...    elements.append(Spacer(1, 0.5*cm))
    ...    elements.append(Paragraph('<i>This report was auto-generated by the University RPA Attendance Bot. Do not reply to this email.</i>', sub_style))
    ...    doc.build(elements)
    ...    print(f"PDF built at ${output_path}")

    Run    python -c "${py_code}"


# ══════════════════════════════════════════════════════════════════
# Send the PDF as an email attachment to the Dean.
# ══════════════════════════════════════════════════════════════════
Send HOD Report Email
    [Documentation]    Emails the PDF report to the Dean using Gmail SMTP.
    [Arguments]    ${pdf_path}    ${count}

    ${today}=    Get Current Date    result_format=%B %Y
    ${subject}=    Set Variable    [Monthly Report] ${count} At-Risk Students — ${today}
    ${body}=    Set Variable
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
    END


# ══════════════════════════════════════════════════════════════════
Write Bot Log
    [Arguments]    ${summary}    ${records}    ${errors}
    ${now}=    Get Current Date    result_format=%Y-%m-%d %H:%M:%S
    ${status}=    Set Variable If    '${errors}' == '${EMPTY}'    success    partial
    TRY
        Execute Sql String
        ...    INSERT INTO core_rpabotlog
        ...        (bot_name, status, started_at, finished_at, summary, records_processed, errors, triggered_by_id)
        ...    VALUES
        ...        ('${BOT_NAME}', '${status}', '${now}', '${now}',
        ...         '${summary}', ${records}, '${errors}', NULL)
        Log To Console    📝 Audit log written.
    EXCEPT    AS    ${err}
        Log To Console    ⚠️ Could not write audit log: ${err}
    END


Print Banner
    [Arguments]    ${title}    ${state}
    Log To Console    \n╔══════════════════════════════════════════════════════╗
    Log To Console    ║  ${title} — ${state}
    Log To Console    ╚══════════════════════════════════════════════════════╝
