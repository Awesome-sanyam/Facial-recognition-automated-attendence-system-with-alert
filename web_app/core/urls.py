from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_login, name='login'),
    path('dashboard/<str:enrollment_number>/', views.dashboard, name='dashboard'),
    path('apply-leave/<str:enrollment_number>/', views.apply_leave, name='apply_leave'),
]