from django.urls import path
from . import views

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

    # ── Alert Config + RPA ────────────────────────────────
    path('faculty/alerts/save/', views.save_alert_config, name='save_alert_config'),
    path('faculty/alerts/run/', views.run_alert_bot, name='run_alert_bot'),
]