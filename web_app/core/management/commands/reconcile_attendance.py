"""
reconcile_attendance.py — Daily absence reconciliation management command.

Usage:
  python manage.py reconcile_attendance
  python manage.py reconcile_attendance --date=2026-09-22
  python manage.py reconcile_attendance --enrollment=ENR123456
"""

from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Student, AttendanceRecord


class Command(BaseCommand):
    help = "Reconcile daily attendance by marking active students without a record as Absent."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Target date in YYYY-MM-DD format (defaults to today in local time)',
            default=None
        )
        parser.add_argument(
            '--enrollment',
            type=str,
            help='Reconcile only a specific student enrollment number',
            default=None
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {date_str}. Use YYYY-MM-DD."))
                return
        else:
            target_date = timezone.localdate()

        enrollment = options.get('enrollment')
        students = Student.objects.all()
        if enrollment:
            students = students.filter(enrollment_number=enrollment)
            if not students.exists():
                self.stderr.write(self.style.ERROR(f"No student found with enrollment: {enrollment}"))
                return

        total_students = students.count()
        already_marked = 0
        marked_absent = 0

        for student in students:
            # Check if record already exists for target date
            exists = AttendanceRecord.objects.filter(student=student, date=target_date).exists()
            if exists:
                already_marked += 1
            else:
                AttendanceRecord.objects.create(
                    student=student,
                    date=target_date,
                    status='Absent'
                )
                marked_absent += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Attendance Reconciliation for {target_date}:\n"
            f"   Total students audited : {total_students}\n"
            f"   Existing records       : {already_marked}\n"
            f"   Newly marked Absent    : {marked_absent}"
        ))
