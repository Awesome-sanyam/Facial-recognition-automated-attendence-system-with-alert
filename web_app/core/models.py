from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ─────────────────────────────────────────────
#  FACULTY
# ─────────────────────────────────────────────

class FacultyProfile(models.Model):
    """
    Extended profile for faculty members.
    Linked 1-to-1 with Django's built-in User.
    Registration sets user.is_active=False until a Django superuser approves it.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='faculty_profile')
    department = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, blank=True)
    is_approved = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.department})"


from .crypto import encrypt_value, decrypt_value


class AlertConfiguration(models.Model):
    """
    Faculty-specific RPA alert settings.
    The Faculty Admin configures this from the dashboard.
    The system reads these values when running the Robot Framework bot.
    """
    faculty = models.OneToOneField(FacultyProfile, on_delete=models.CASCADE, related_name='alert_config')
    gmail_address = models.EmailField(blank=True)
    gmail_app_password = models.CharField(max_length=255, blank=True)
    alert_threshold = models.IntegerField(
        default=75,
        help_text="Students below this attendance % will receive an alert."
    )
    email_alerts_enabled = models.BooleanField(default=True)
    alert_email_subject = models.CharField(
        max_length=200,
        default="URGENT: Low Attendance Warning"
    )
    alert_email_body = models.TextField(
        default=(
            "Dear Parent/Guardian,\n\n"
            "This is an automated alert from the University Attendance System.\n"
            "Your ward {student_name} currently has {attendance_percentage}% attendance, "
            "which is below the mandatory {threshold}% threshold.\n\n"
            "Please contact the administration immediately.\n\n"
            "Regards,\nUniversity Administration"
        )
    )

    # Twilio SMS Config
    twilio_account_sid = models.CharField(max_length=100, blank=True)
    twilio_auth_token = models.CharField(max_length=255, blank=True)
    twilio_from_number = models.CharField(max_length=20, blank=True)
    sms_alerts_enabled = models.BooleanField(default=False)
    sms_alert_body = models.TextField(
        default=(
            "URGENT: {student_name} has {attendance_percentage}% attendance "
            "(below {threshold}%). Contact administration."
        )
    )

    # ── NEW: Dean / HOD Report Config ────────────────────────────────────────
    dean_email = models.EmailField(
        blank=True,
        help_text="Dean's email address for monthly HOD PDF reports."
    )
    hod_report_threshold = models.IntegerField(
        default=75,
        help_text="Students below this % are included in the monthly HOD report."
    )

    last_run_at = models.DateTimeField(null=True, blank=True)

    def get_decrypted_gmail_password(self) -> str:
        return decrypt_value(self.gmail_app_password)

    def set_encrypted_gmail_password(self, plain_text: str):
        self.gmail_app_password = encrypt_value(plain_text)

    def get_decrypted_twilio_token(self) -> str:
        return decrypt_value(self.twilio_auth_token)

    def set_encrypted_twilio_token(self, plain_text: str):
        self.twilio_auth_token = encrypt_value(plain_text)

    def __str__(self):
        return f"Alert Config — {self.faculty}"


# ─────────────────────────────────────────────
#  STUDENTS
# ─────────────────────────────────────────────

class Student(models.Model):
    name = models.CharField(max_length=100)
    enrollment_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=15)
    department = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(
        default=1,
        choices=[(1, '1st Year'), (2, '2nd Year'), (3, '3rd Year'), (4, '4th Year')]
    )
    pin_code = models.CharField(max_length=128, blank=True, default='')
    face_encoding = models.TextField(blank=True, null=True)
    added_by = models.ForeignKey(
        FacultyProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students_added'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def attendance_percentage(self):
        # Exclude 'Excused' (approved leaves) from total classes denominator
        records = self.attendancerecord_set.all()
        total_records = records.count()
        if total_records == 0:
            return 0.0
        countable_records = records.exclude(status='Excused').count()
        if countable_records == 0:
            return 100.0
        present_count = records.filter(status='Present').count()
        return round((present_count / countable_records) * 100, 2)

    @property
    def calculated_percentage(self):
        """
        High-performance property that reuses annotated DB counts if present,
        preventing N+1 queries in templates and bulk views.
        """
        if hasattr(self, 'total_classes') and hasattr(self, 'present_count'):
            excused = getattr(self, 'excused_count', 0)
            countable = self.total_classes - excused
            if self.total_classes == 0:
                return 0.0
            if countable <= 0:
                return 100.0
            return round((self.present_count / countable) * 100, 2)
        return self.attendance_percentage

    @property
    def needs_alert(self):
        return self.attendance_percentage < 75

    def __str__(self):
        return f"{self.name} ({self.enrollment_number})"


# ─────────────────────────────────────────────
#  ATTENDANCE & LEAVES
# ─────────────────────────────────────────────

class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    time = models.TimeField(auto_now_add=True)
    status = models.CharField(
        max_length=15,
        choices=[('Present', 'Present'), ('Absent', 'Absent'), ('Excused', 'Excused')],
        default='Present'
    )

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date', '-time']

    def __str__(self):
        return f"{self.student.name} — {self.date} — {self.status}"


class LeaveApplication(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date_requested = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=15,
        choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
        default='Pending'
    )
    reviewed_by = models.ForeignKey(
        FacultyProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='leaves_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Leave: {self.student.name} — {self.date_requested} [{self.status}]"


# ─────────────────────────────────────────────
#  NEW: HOLIDAY CALENDAR
#  Bot 3 — Holiday Sync reads academic_calendar.xlsx
#  and stores entries here so the attendance system
#  can prevent marking absences on holidays.
# ─────────────────────────────────────────────

class HolidayCalendar(models.Model):
    """
    Stores academic holiday / event dates synced from academic_calendar.xlsx
    by the Holiday Sync RPA bot (Bot 3).

    When a faculty tries to mark attendance, the system checks this table.
    If today's date is a holiday, marking is blocked with a clear message.
    """
    date = models.DateField(unique=True)
    name = models.CharField(max_length=200, help_text="Holiday or event name, e.g. 'Diwali'")
    holiday_type = models.CharField(
        max_length=50,
        choices=[
            ('National', 'National Holiday'),
            ('University', 'University Holiday'),
            ('Exam', 'Examination / No Classes'),
            ('Event', 'Academic Event'),
            ('Other', 'Other'),
        ],
        default='University'
    )
    synced_at = models.DateTimeField(auto_now=True)   # Updated every time bot runs
    synced_by_bot = models.BooleanField(default=True)  # False if manually added via admin

    class Meta:
        ordering = ['date']
        verbose_name = 'Holiday'
        verbose_name_plural = 'Holiday Calendar'

    def __str__(self):
        return f"{self.date} — {self.name} ({self.holiday_type})"

    @classmethod
    def is_holiday(cls, check_date) -> bool:
        """Returns True if the given date is a registered holiday."""
        return cls.objects.filter(date=check_date).exists()

    @classmethod
    def get_holiday_name(cls, check_date) -> str | None:
        """Returns the holiday name for a date, or None if not a holiday."""
        entry = cls.objects.filter(date=check_date).first()
        return entry.name if entry else None


# ─────────────────────────────────────────────
#  NEW: RPA BOT AUDIT LOG
#  Tracks every bot execution for the dashboard.
#  All 5 bots write a log entry after each run.
# ─────────────────────────────────────────────

class RPABotLog(models.Model):
    """
    Audit trail for all RPA bot executions.
    Displayed on the Faculty Dashboard under the 'RPA Bots' tab.
    """
    BOT_CHOICES = [
        ('leave_processor',  'Bot 1 — Auto-Leave Processor'),
        ('hod_report',       'Bot 2 — Monthly HOD PDF Report'),
        ('holiday_sync',     'Bot 3 — Holiday Sync'),
        ('ptm_escalation',   'Bot 4 — PTM Escalation'),
        ('db_backup',        'Bot 5 — Nightly DB Backup'),
        ('alert_bot',        'Existing — Weekly Alert Bot'),
    ]
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('partial', 'Partial Success'),
        ('failed',  'Failed'),
        ('running', 'Running'),
    ]

    bot_name = models.CharField(max_length=50, choices=BOT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, help_text="Human-readable result summary.")
    records_processed = models.IntegerField(default=0)
    errors = models.TextField(blank=True, help_text="Any error messages encountered.")
    triggered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="The faculty user who triggered this bot run."
    )

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'RPA Bot Log'
        verbose_name_plural = 'RPA Bot Logs'

    def __str__(self):
        return f"[{self.get_bot_name_display()}] {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"

    def mark_done(self, status, summary, records=0, errors=''):
        """Convenience method to finalise a log entry."""
        self.status = status
        self.summary = summary
        self.records_processed = records
        self.errors = errors
        self.finished_at = timezone.now()
        self.save()
