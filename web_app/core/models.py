from django.db import models
from django.contrib.auth.models import User


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


class AlertConfiguration(models.Model):
    """
    Faculty-specific RPA alert settings.
    The Faculty Admin configures this from the dashboard.
    The system reads these values when running the Robot Framework bot.
    """
    faculty = models.OneToOneField(FacultyProfile, on_delete=models.CASCADE, related_name='alert_config')
    gmail_address = models.EmailField(blank=True)
    gmail_app_password = models.CharField(max_length=64, blank=True)
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
    twilio_auth_token = models.CharField(max_length=100, blank=True)
    twilio_from_number = models.CharField(max_length=20, blank=True)
    sms_alerts_enabled = models.BooleanField(default=False)
    sms_alert_body = models.TextField(
        default=(
            "URGENT: {student_name} has {attendance_percentage}% attendance "
            "(below {threshold}%). Contact administration."
        )
    )

    last_run_at = models.DateTimeField(null=True, blank=True)

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
    face_encoding = models.TextField(blank=True, null=True)
    added_by = models.ForeignKey(
        FacultyProfile, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='students_added'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def attendance_percentage(self):
        total_records = self.attendancerecord_set.count()
        if total_records == 0:
            return 0
        present_count = self.attendancerecord_set.filter(status='Present').count()
        return round((present_count / total_records) * 100, 2)

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
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[('Present', 'Present'), ('Absent', 'Absent')],
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
