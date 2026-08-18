"""
Smoke tests for the Attendance System.
Run with: python web_app/manage.py test core --verbosity=2
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Student, FacultyProfile, AlertConfiguration, AttendanceRecord, LeaveApplication
from datetime import date


class PublicPageTests(TestCase):
    """Pages that should be accessible without login."""

    def test_home_page_200(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_student_login_page_200(self):
        response = self.client.get(reverse('student_login'))
        self.assertEqual(response.status_code, 200)

    def test_faculty_login_page_200(self):
        response = self.client.get(reverse('faculty_login'))
        self.assertEqual(response.status_code, 200)

    def test_faculty_register_page_200(self):
        response = self.client.get(reverse('faculty_register'))
        self.assertEqual(response.status_code, 200)

    def test_faculty_dashboard_redirects_when_not_logged_in(self):
        """Dashboard must redirect to login if not authenticated."""
        response = self.client.get(reverse('faculty_dashboard'))
        self.assertIn(response.status_code, [301, 302])


class StudentLoginTests(TestCase):
    """Student portal login flow."""

    def setUp(self):
        self.student = Student.objects.create(
            name='Test Student',
            enrollment_number='TEST001',
            parent_email='parent@example.com',
            parent_phone='9876543210',
        )

    def test_valid_enrollment_redirects_to_dashboard(self):
        response = self.client.post(reverse('student_login'), {'enrollment_number': 'TEST001'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('TEST001', response['Location'])

    def test_invalid_enrollment_shows_error(self):
        response = self.client.post(reverse('student_login'), {'enrollment_number': 'INVALID999'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No student found')

    def test_duplicate_leave_rejected(self):
        """Submitting a leave for the same date twice should warn, not create two records."""
        session = self.client.session
        session['student_enrollment'] = 'TEST001'
        session.save()
        leave_url = reverse('apply_leave', kwargs={'enrollment_number': 'TEST001'})
        # First application
        self.client.post(leave_url, {'date_requested': '2025-01-15', 'reason': 'Sick'})
        # Second application for same date — should be blocked
        self.client.post(leave_url, {'date_requested': '2025-01-15', 'reason': 'Sick again'})
        count = LeaveApplication.objects.filter(
            student=self.student, date_requested='2025-01-15'
        ).count()
        self.assertEqual(count, 1, "Duplicate leave application should be blocked")

    def test_empty_reason_rejected(self):
        """Leave application with empty reason should not be created."""
        session = self.client.session
        session['student_enrollment'] = 'TEST001'
        session.save()
        self.client.post(
            reverse('apply_leave', kwargs={'enrollment_number': 'TEST001'}),
            {'date_requested': '2025-02-01', 'reason': ''}
        )
        self.assertEqual(LeaveApplication.objects.filter(student=self.student).count(), 0)


class FacultyTests(TestCase):
    """Faculty registration, login, and dashboard."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testfaculty', password='testpass123',
            is_staff=True, is_active=True
        )
        self.profile = FacultyProfile.objects.create(
            user=self.user, department='CS', is_approved=True
        )
        self.alert_config = AlertConfiguration.objects.create(faculty=self.profile)

    def test_faculty_login_success(self):
        response = self.client.post(reverse('faculty_login'), {
            'username': 'testfaculty',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_faculty_dashboard_loads(self):
        self.client.login(username='testfaculty', password='testpass123')
        response = self.client.get(reverse('faculty_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_add_student(self):
        self.client.login(username='testfaculty', password='testpass123')
        response = self.client.post(reverse('add_student'), {
            'name': 'New Student',
            'enrollment_number': 'ENR9999',
            'parent_email': 'p@p.com',
            'parent_phone': '1234567890',
            'department': 'CS',
            'year': 1,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Student.objects.filter(enrollment_number='ENR9999').exists())

    def test_add_student_duplicate_rejected(self):
        """Adding a student with an existing enrollment number must not create a duplicate."""
        Student.objects.create(
            name='Existing', enrollment_number='DUP001',
            parent_email='e@e.com', parent_phone='111'
        )
        self.client.login(username='testfaculty', password='testpass123')
        self.client.post(reverse('add_student'), {
            'name': 'Duplicate', 'enrollment_number': 'DUP001',
            'parent_email': 'x@x.com', 'parent_phone': '222',
            'department': 'CS', 'year': 1,
        })
        self.assertEqual(Student.objects.filter(enrollment_number='DUP001').count(), 1)

    def test_alert_threshold_clamped_at_100(self):
        """A threshold of 999 must be clamped to 100."""
        self.client.login(username='testfaculty', password='testpass123')
        self.client.post(reverse('save_alert_config'), {
            'gmail_address': 'test@gmail.com',
            'gmail_app_password': 'testpass',
            'alert_threshold': '999',
            'alert_email_subject': 'Test',
            'alert_email_body': 'Body {student_name} {attendance_percentage} {threshold}',
            'sms_alert_body': 'SMS {student_name} {attendance_percentage} {threshold}',
        })
        self.alert_config.refresh_from_db()
        self.assertLessEqual(self.alert_config.alert_threshold, 100)

    def test_manage_leave_get_does_not_approve(self):
        """GET on manage_leave must redirect WITHOUT approving the leave."""
        student = Student.objects.create(
            name='S', enrollment_number='E1', parent_email='e@e.com', parent_phone='1'
        )
        leave = LeaveApplication.objects.create(
            student=student, date_requested=date.today(), reason='test'
        )
        self.client.login(username='testfaculty', password='testpass123')
        response = self.client.get(
            reverse('manage_leave', kwargs={'leave_id': leave.id, 'action': 'approve'})
        )
        self.assertEqual(response.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'Pending')  # Must NOT be approved

    def test_manage_leave_post_approves(self):
        """POST on manage_leave/approve must set status to Approved."""
        student = Student.objects.create(
            name='S2', enrollment_number='E2', parent_email='e2@e.com', parent_phone='2'
        )
        leave = LeaveApplication.objects.create(
            student=student, date_requested=date.today(), reason='test'
        )
        self.client.login(username='testfaculty', password='testpass123')
        self.client.post(
            reverse('manage_leave', kwargs={'leave_id': leave.id, 'action': 'approve'})
        )
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'Approved')


class AttendanceTests(TestCase):
    """Attendance model and percentage calculation."""

    def _make_student(self, enr):
        return Student.objects.create(
            name=f'Student {enr}', enrollment_number=enr,
            parent_email=f'{enr}@test.com', parent_phone='111'
        )

    def test_zero_attendance_when_no_records(self):
        s = self._make_student('ATT000')
        self.assertEqual(s.attendance_percentage, 0)

    def test_100_percent_all_present(self):
        """Single record marked Present = 100%."""
        s = self._make_student('ATT100')
        AttendanceRecord.objects.create(student=s, status='Present')
        self.assertEqual(s.attendance_percentage, 100.0)

    def test_0_percent_all_absent(self):
        """Single record marked Absent = 0%."""
        s = self._make_student('ATT0')
        AttendanceRecord.objects.create(student=s, status='Absent')
        self.assertEqual(s.attendance_percentage, 0.0)

    def test_needs_alert_below_75(self):
        """Student with 0% attendance needs an alert."""
        s = self._make_student('ATTALERT')
        AttendanceRecord.objects.create(student=s, status='Absent')
        self.assertTrue(s.needs_alert)

    def test_no_alert_at_100_percent(self):
        """Student with 100% attendance does not need an alert."""
        s = self._make_student('ATTOK')
        AttendanceRecord.objects.create(student=s, status='Present')
        self.assertFalse(s.needs_alert)

