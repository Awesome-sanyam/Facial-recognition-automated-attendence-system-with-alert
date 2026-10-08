from django.urls import path
from . import views
from . import rpa_runner

urlpatterns = [
    # ── Landing ──────────────────────────────────────────
    path('', views.home, name='home'),

    # ── Student Portal ────────────────────────────────────
    path('student/login/', views.student_login, name='student_login'),
    path('student/logout/', views.student_logout, name='student_logout'),
    path('student/face-login/', views.face_login_api, name='face_login_api'),
    path('dashboard/<str:enrollment_number>/', views.dashboard, name='dashboard'),
    path('apply-leave/<str:enrollment_number>/', views.apply_leave, name='apply_leave'),

    # ── Faculty Registration Flow ─────────────────────────
    path('faculty/register/', views.faculty_register, name='faculty_register'),
    path('faculty/pending/', views.faculty_pending, name='faculty_pending'),

    # ── Faculty Auth ──────────────────────────────────────
    path('faculty/login/', views.faculty_login, name='faculty_login'),
    path('faculty/logout/', views.faculty_logout, name='faculty_logout'),

    # ── Faculty Dashboard ─────────────────────────────────
    path('faculty/dashboard/', views.faculty_dashboard, name='faculty_dashboard'),

    # ── Student CRUD ──────────────────────────────────────
    path('faculty/student/add/', views.add_student, name='add_student'),
    path('faculty/student/delete/<int:student_id>/', views.delete_student, name='delete_student'),

    # ── Leave Management ──────────────────────────────────
    path('faculty/leave/<int:leave_id>/<str:action>/', views.manage_leave, name='manage_leave'),

    # ── Alert Config + Legacy RPA Bot ─────────────────────
    path('faculty/alerts/save/', views.save_alert_config, name='save_alert_config'),
    path('faculty/alerts/run/', views.run_alert_bot, name='run_alert_bot'),

    # ── NEW: Live Automation Hub (judge-facing full page) ─
    path('automation-hub/', views.automation_hub, name='automation_hub'),

    # ── NEW: Live Feed JSON API (polled every 4 s by JS) ──
    path('api/automation-feed/', views.automation_hub_feed_api, name='automation_hub_feed_api'),

    # ── NEW: Bot Log POST API (called by Robot Framework) ─
    path('api/bot-log/', views.bot_log_api, name='bot_log_api'),

    # ── NEW: 5 Enterprise RPA Bots ───────────────────────
    # Bot 1 — Auto-Leave Processor
    path('faculty/bots/leave-processor/', rpa_runner.run_leave_processor_bot, name='run_leave_processor_bot'),

    # Bot 2 — Monthly HOD PDF Report
    path('faculty/bots/hod-report/', rpa_runner.run_hod_report_bot, name='run_hod_report_bot'),

    # Bot 3 — Holiday Sync (reads academic_calendar.xlsx)
    path('faculty/bots/holiday-sync/', rpa_runner.run_holiday_sync_bot, name='run_holiday_sync_bot'),

    # Bot 4 — PTM Escalation (< 50% attendance parents)
    path('faculty/bots/ptm-escalation/', rpa_runner.run_ptm_escalation_bot, name='run_ptm_escalation_bot'),

    # Bot 5 — Nightly DB Backup + IT Health Report
    path('faculty/bots/db-backup/', rpa_runner.run_db_backup_bot, name='run_db_backup_bot'),
]