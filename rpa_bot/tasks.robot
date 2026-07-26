*** Settings ***
Documentation     University Attendance RPA Bot. Logs into Django Admin and sends alerts.
Library           SeleniumLibrary
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587

*** Variables ***
${ADMIN_URL}      http://127.0.0.1:8000/admin
${ADMIN_USER}     # Your Django superuser
${ADMIN_PASS}     # Your Django password

${GMAIL_USER}     # Your actual Gmail address
${GMAIL_PASS}     # The 16-letter App Password (NO SPACES)

*** Tasks ***
Process Weekly Attendance Alerts
    Open Admin Portal
    Login To System
    Navigate To Students Table
    
    # Authorize the email server securely
    Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}
    
    # In the final version, this will loop through the low-attendance students.
    # For now, we test the dispatch system with a single hardcoded alert.
    Send Warning Email    # ENTER_A_TEST_EMAIL_ADDRESS_HERE    Student Name    65%
    
    Log    Successfully dispatched warning emails!
    [Teardown]    Close Browser

*** Keywords ***
Open Admin Portal
    Open Browser    ${ADMIN_URL}    chrome
    Maximize Browser Window

Login To System
    Input Text        id:id_username    ${ADMIN_USER}
    Input Password    id:id_password    ${ADMIN_PASS}
    Click Button      css:input[type='submit']
    Wait Until Page Contains    Site administration

Navigate To Students Table
    Click Link    link:Students
    Wait Until Page Contains    Select student to change

Send Warning Email
    [Arguments]    ${recipient_email}    ${student_name}    ${attendance_percentage}
    ${subject}=    Set Variable    URGENT: Low Attendance Warning - ${student_name}
    ${body}=       Set Variable    Dear Parent/Student,\n\nThis is an automated alert from the University System. The current attendance for ${student_name} has dropped to ${attendance_percentage}, which is below the mandatory 75% threshold.\n\nPlease submit a leave application or contact the administration immediately.\n\nRegards,\nAutomated Admin Bot
    
    Send Message    sender=${GMAIL_USER}    recipients=${recipient_email}    subject=${subject}    body=${body}