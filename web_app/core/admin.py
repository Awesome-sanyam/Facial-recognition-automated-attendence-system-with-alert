from django.contrib import admin
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import (
    FacultyProfile, AlertConfiguration,
    Student, AttendanceRecord, LeaveApplication,
    HolidayCalendar, RPABotLog, BotActivityLog,
)


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


# ─────────────────────────────────────────────
#  NEW: HOLIDAY CALENDAR ADMIN
# ─────────────────────────────────────────────

@admin.register(HolidayCalendar)
class HolidayCalendarAdmin(admin.ModelAdmin):
    """
    Admin view for the Holiday Calendar.
    Faculty can manually add holidays here, or the
    Holiday Sync Bot (Bot 3) auto-populates them from academic_calendar.xlsx.
    """
    list_display  = ('date', 'name', 'holiday_type', 'synced_by_bot', 'synced_at')
    list_filter   = ('holiday_type', 'synced_by_bot')
    search_fields = ('name',)
    ordering      = ('date',)
    readonly_fields = ('synced_at',)
    list_per_page = 50

    def get_readonly_fields(self, request, obj=None):
        # Dates synced by bot should not be edited manually
        if obj and obj.synced_by_bot:
            return self.readonly_fields + ('date', 'synced_by_bot')
        return self.readonly_fields


# ─────────────────────────────────────────────
#  NEW: RPA BOT LOG ADMIN
# ─────────────────────────────────────────────

@admin.register(RPABotLog)
class RPABotLogAdmin(admin.ModelAdmin):
    """
    Read-only audit trail for all RPA bot executions.
    Displays coloured status badges and links back to triggering user.
    """
    list_display  = ('get_bot_name_display', 'status_badge', 'records_processed',
                     'started_at', 'finished_at', 'triggered_by')
    list_filter   = ('bot_name', 'status', 'started_at')
    search_fields = ('summary', 'errors')
    readonly_fields = ('bot_name', 'status', 'started_at', 'finished_at',
                       'summary', 'records_processed', 'errors', 'triggered_by')
    ordering      = ('-started_at',)
    list_per_page = 50

    def status_badge(self, obj):
        color_map = {
            'success': '#16a34a',
            'partial': '#d97706',
            'failed':  '#dc2626',
            'running': '#2563eb',
        }
        color = color_map.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:700;text-transform:uppercase">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        # Logs are written only by bots — not manually
        return False


# ─────────────────────────────────────────────
#  NEW: BOT ACTIVITY LOG ADMIN
# ─────────────────────────────────────────────

@admin.register(BotActivityLog)
class BotActivityLogAdmin(admin.ModelAdmin):
    """
    Read-only granular audit trail for individual bot actions.
    Displayed in the Live Automation Hub terminal feed.
    """
    list_display  = ('timestamp', 'get_bot_name_display', 'status_badge', 'action', 'target')
    list_filter   = ('bot_name', 'status', 'timestamp')
    search_fields = ('action', 'target', 'detail')
    readonly_fields = ('bot_name', 'action', 'target', 'status', 'timestamp', 'detail', 'rpa_log')
    ordering      = ('-timestamp',)
    list_per_page = 100
    date_hierarchy = 'timestamp'

    def status_badge(self, obj):
        color_map = {
            'success': '#16a34a',
            'info':    '#2563eb',
            'warning': '#d97706',
            'error':   '#dc2626',
        }
        color = color_map.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:700;text-transform:uppercase">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
