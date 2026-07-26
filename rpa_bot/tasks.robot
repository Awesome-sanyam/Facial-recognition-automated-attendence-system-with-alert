*** Settings ***
Documentation     University Attendance RPA Bot. Audits Django Admin and sends dynamic alerts.
Library           SeleniumLibrary
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587
Library           String

*** Variables ***
# Using the direct URL to the Students table saves the bot an extra click
${ADMIN_URL}      http://127.0.0.1:8000/admin/core/student/
${ADMIN_USER}     admin
${ADMIN_PASS}     admin123

${GMAIL_USER}     sanyam.gehlot@gmail.com
${GMAIL_PASS}     tgvvmvyscqvchpay

*** Tasks ***
Process Weekly Attendance Alerts
    Open Admin Portal
    Login To System
    Authorize Email Server
    Audit Attendance Records
    Log    Weekly audit completed successfully!
    [Teardown]    Close Browser

*** Keywords ***
Open Admin Portal
    Open Browser    ${ADMIN_URL}    chrome
    Maximize Browser Window

Login To System
    Input Text        id:id_username    ${ADMIN_USER}
    Input Password    id:id_password    ${ADMIN_PASS}
    Click Button      css:input[type='submit']
    Wait Until Page Contains    Select student to change

Authorize Email Server
    Authorize    account=${GMAIL_USER}    password=${GMAIL_PASS}

Audit Attendance Records
    # Locate all rows in the Django admin data table
    ${rows}=    Get WebElements    xpath://*[@id="result_list"]/tbody/tr
    
    FOR    ${row}    IN    @{rows}
        # Scrape data from specific columns using Django's auto-generated CSS classes
        ${name}=          Get Text    ${row}//th[@class='field-name']
        ${email}=         Get Text    ${row}//td[@class='field-parent_email']
        ${percent_str}=   Get Text    ${row}//td[@class='field-get_attendance_percentage']
        
        # Strip the '%' sign and convert the string to a decimal number for math comparison
        ${percent_num}=   Remove String    ${percent_str}    %
        ${percent_val}=   Convert To Number    ${percent_num}
        
        # Apply the University Business Rule
        IF    ${percent_val} < 75.0
            Log    Low attendance detected: Sending alert to ${name} (${percent_val}%) at ${email}
            Send Warning Email    ${email}    ${name}    ${percent_str}
        ELSE
            Log    ${name} has compliant attendance (${percent_val}%). No action required.
        END
    END

Send Warning Email
    [Arguments]    ${recipient_email}    ${student_name}    ${attendance_percentage}
    ${subject}=    Set Variable    URGENT: Low Attendance Warning - ${student_name}
    ${body}=       Set Variable    Dear Parent/Student,\n\nThis is an automated alert from the University System. The current attendance for ${student_name} has dropped to ${attendance_percentage}, which is below the mandatory 75% threshold.\n\nPlease submit a leave application or contact the administration immediately.\n\nRegards,\nAutomated Admin Bot
    
    Send Message    sender=${GMAIL_USER}    recipients=${recipient_email}    subject=${subject}    body=${body}