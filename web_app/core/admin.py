from django.contrib import admin
from .models import Student, AttendanceRecord, LeaveApplication

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'enrollment_number', 'parent_email', 'get_attendance_percentage')
    search_fields = ('name', 'enrollment_number')

    def get_attendance_percentage(self, obj):
        return f"{obj.attendance_percentage}%"
    get_attendance_percentage.short_description = 'Attendance %'

@admin.register(AttendanceRecord)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'time', 'status')
    list_filter = ('date', 'status') # Crucial for the RPA bot to filter data easily
    search_fields = ('student__name',)

@admin.register(LeaveApplication)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ('student', 'date_requested', 'status')
    list_filter = ('status',)
