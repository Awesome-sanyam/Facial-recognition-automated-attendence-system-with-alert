from django.urls import path
from . import views

urlpatterns = [
    # Landing
    path('', views.home, name='home'),

    # Student Portal
    path('student/login/', views.student_login, name='student_login'),
    path('student/logout/', views.student_logout, name='student_logout'),
    path('dashboard/<str:enrollment_number>/', views.dashboard, name='dashboard'),
    path('apply-leave/<str:enrollment_number>/', views.apply_leave, name='apply_leave'),

    # Faculty Portal
    path('faculty/login/', views.faculty_login, name='faculty_login'),
    path('faculty/logout/', views.faculty_logout, name='faculty_logout'),
    path('faculty/dashboard/', views.faculty_dashboard, name='faculty_dashboard'),
    path('faculty/leave/<int:leave_id>/<str:action>/', views.manage_leave, name='manage_leave'),
]