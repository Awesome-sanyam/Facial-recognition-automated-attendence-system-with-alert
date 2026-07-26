*** Settings ***
Documentation     Automated warning emails/SMS for low attendance.

*** Variables ***
${DB_HOST}        localhost
${DB_NAME}        attendance_db
${DB_USER}        postgres
${DB_PASSWORD}    postgres

*** Tasks ***
Check Attendance and Send Alerts
    Log    Starting Attendance Check RPA Task
    # Query database for <75% attendance
    # Send Email/SMS alerts
    Log    Task Completed
