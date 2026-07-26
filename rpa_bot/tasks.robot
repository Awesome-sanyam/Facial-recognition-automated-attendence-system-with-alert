*** Settings ***
Documentation     University Attendance RPA Bot. Audits Django Admin and sends dynamic alerts.
Library           SeleniumLibrary
Library           EmailLibrary.py    smtp_server=smtp.gmail.com    smtp_port=587
Library           SmsLibrary.py
Library           String

*** Variables ***
# Using the direct URL to the Students table saves the bot an extra click
${ADMIN_URL}      http://127.0.0.1:8000/admin/core/student/
${ADMIN_USER}     admin
${ADMIN_PASS}     admin123

${GMAIL_USER}     sanyam.gehlot@gmail.com
${GMAIL_PASS}     tgvvmvyscqvchpay
${TWILIO_SID}      
${TWILIO_TOKEN}    
${TWILIO_FROM}     
${SMS_ENABLED}     False

*** Tasks ***
Process Weekly Attendance Alerts
    Open Admin Portal
    Login To System
    Authorize Email Server
    Authorize SMS Server
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

Authorize SMS Server
    Authorize SMS    account_sid=${TWILIO_SID}    auth_token=${TWILIO_TOKEN}    from_number=${TWILIO_FROM}

Audit Attendance Records
    # Locate the number of rows in the Django admin data table
    ${row_count}=    Get Element Count    xpath://*[@id="result_list"]/tbody/tr
    
    FOR    ${i}    IN RANGE    1    ${row_count} + 1
        # Scrape data from specific columns using Django's auto-generated CSS classes by row index
        ${name}=          Get Text    xpath://*[@id="result_list"]/tbody/tr[${i}]/th[contains(@class, 'field-name')]
        ${email}=         Get Text    xpath://*[@id="result_list"]/tbody/tr[${i}]/td[contains(@class, 'field-parent_email')]
        ${phone}=         Get Text    xpath://*[@id="result_list"]/tbody/tr[${i}]/td[contains(@class, 'field-parent_phone')]
        ${percent_str}=   Get Text    xpath://*[@id="result_list"]/tbody/tr[${i}]/td[contains(@class, 'field-get_attendance_percentage')]
        
        # Strip the '%' sign and convert the string to a decimal number for math comparison
        ${percent_num}=   Remove String    ${percent_str}    %
        ${percent_val}=   Convert To Number    ${percent_num}
        
        # Apply the University Business Rule
        IF    ${percent_val} < 75.0
            Log    Low attendance detected: Sending alerts to ${name} (${percent_val}%) at ${email} and ${phone}
            Send Warning Email    ${email}    ${name}    ${percent_str}
            
            IF    '${SMS_ENABLED}' == 'True'
                Send Warning SMS    ${phone}    ${name}    ${percent_str}
            END
        ELSE
            Log    ${name} has compliant attendance (${percent_val}%). No action required.
        END
    END

Send Warning Email
    [Arguments]    ${recipient_email}    ${student_name}    ${attendance_percentage}
    ${subject}=    Set Variable    URGENT: Low Attendance Warning - ${student_name}
    ${body}=       Set Variable    Dear Parent/Student,\n\nThis is an automated alert from the University System. The current attendance for ${student_name} has dropped to ${attendance_percentage}, which is below the mandatory 75% threshold.\n\nPlease submit a leave application or contact the administration immediately.\n\nRegards,\nAutomated Admin Bot
    
    Send Message    sender=${GMAIL_USER}    recipients=${recipient_email}    subject=${subject}    body=${body}

Send Warning SMS
    [Arguments]    ${recipient_phone}    ${student_name}    ${attendance_percentage}
    ${body}=       Set Variable    URGENT: ${student_name} has ${attendance_percentage} attendance (below 75%). Contact administration immediately.
    
    Send Sms    to_number=${recipient_phone}    body=${body}