*** Settings ***
Documentation     University Attendance RPA Bot. Logs into Django Admin to audit attendance.
Library           SeleniumLibrary

*** Variables ***
${ADMIN_URL}      http://127.0.0.1:8000/admin
${ADMIN_USER}     # Type the superuser name you created here
${ADMIN_PASS}     # Type the superuser password you created here

*** Tasks ***
Process Weekly Attendance Alerts
    Open Admin Portal
    Login To System
    Navigate To Students Table
    Log    Successfully logged into the university system and accessed records as a digital worker!
    Sleep    3s    # Pausing just so you can watch it work before it closes
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
    # Clicks the 'Students' link in the Django Admin panel
    Click Link    link:Students
    Wait Until Page Contains    Select student to change