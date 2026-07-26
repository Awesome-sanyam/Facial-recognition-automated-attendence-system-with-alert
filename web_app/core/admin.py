from django.contrib import admin
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import FacultyProfile, AlertConfiguration, Student, AttendanceRecord, LeaveApplication


# ─────────────────────────────────────────────
#  FACULTY ADMIN
# ─────────────────────────────────────────────

@admin.register(FacultyProfile)
class FacultyProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'get_username', 'department', 'phone', 'approval_status', 'registered_at')
    list_filter = ('is_approved', 'department')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'department')
    actions = ['approve_faculty', 'revoke_faculty']
    readonly_fields = ('registered_at',)
    list_per_page = 25

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Full Name'

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'

    def approval_status(self, obj):
        if obj.is_approved:
            return mark_safe('<span style="color:#16a34a;font-weight:700">✓ Approved</span>')
        return mark_safe('<span style="color:#dc2626;font-weight:700">⏳ Pending Approval</span>')
    approval_status.short_description = 'Status'

    @admin.action(description='✅ Approve selected faculty registrations')
    def approve_faculty(self, request, queryset):
        count = 0
        for profile in queryset:
            if not profile.is_approved:
                profile.is_approved = True
                profile.user.is_active = True
                profile.user.is_staff = True
                profile.user.save()
                profile.save()
                # Auto-create AlertConfiguration for them
                AlertConfiguration.objects.get_or_create(faculty=profile)
                count += 1
        self.message_user(request, f'{count} faculty member(s) approved and activated successfully.')

    @admin.action(description='❌ Revoke faculty access')
    def revoke_faculty(self, request, queryset):
        count = 0
        for profile in queryset:
            if profile.is_approved:
                profile.is_approved = False
                profile.user.is_active = False
                profile.user.is_staff = False
                profile.user.save()
                profile.save()
                count += 1
        self.message_user(request, f'{count} faculty member(s) revoked.')


@admin.register(AlertConfiguration)
class AlertConfigAdmin(admin.ModelAdmin):
    list_display = ('faculty', 'gmail_address', 'alert_threshold', 'email_alerts_enabled', 'last_run_at')
    list_filter = ('email_alerts_enabled',)
    list_per_page = 25


# ─────────────────────────────────────────────
#  STUDENT ADMIN
# ─────────────────────────────────────────────

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'enrollment_number', 'department', 'year', 'parent_email', 'parent_phone', 'get_attendance_percentage', 'added_by')
    search_fields = ('name', 'enrollment_number', 'department')
    list_filter = ('year', 'department', 'added_by')
    readonly_fields = ('created_at',)
    list_per_page = 25

    def get_attendance_percentage(self, obj):
        pct = obj.attendance_percentage
        color = '#16a34a' if pct >= 75 else '#dc2626'
        return format_html('<span style="color:{};font-weight:700">{}%</span>', color, pct)
    get_attendance_percentage.short_description = 'Attendance %'


# ─────────────────────────────────────────────
#  ATTENDANCE & LEAVE ADMIN
# ─────────────────────────────────────────────

@admin.register(AttendanceRecord)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'time', 'status')
    list_filter = ('date', 'status')
    search_fields = ('student__name',)
    list_per_page = 25


@admin.register(LeaveApplication)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ('student', 'date_requested', 'status', 'reviewed_by', 'reviewed_at')
    list_filter = ('status',)
    readonly_fields = ('reviewed_at',)
    list_per_page = 25
