from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q
import os, sys, json, smtplib
from email.message import EmailMessage
import logging

# Module-level logger — configured in settings.py LOGGING dict
logger = logging.getLogger(__name__)

# Add face_recognition module to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'face_recognition'))
try:
    from face_login import recognize_face_from_b64
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

from .models import (
    FacultyProfile, AlertConfiguration,
    Student, AttendanceRecord, LeaveApplication,
    HolidayCalendar, RPABotLog,
)


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def is_approved_faculty(user):
    if not user.is_authenticated:
        return False
    # Superusers always get access
    if user.is_superuser:
        return True
    return (
        user.is_staff and
        hasattr(user, 'faculty_profile') and
        user.faculty_profile.is_approved
    )


# ─────────────────────────────────────────────
#  LANDING
# ─────────────────────────────────────────────

def home(request):
    return render(request, 'core/home.html')


# ─────────────────────────────────────────────
#  STUDENT PORTAL
# ─────────────────────────────────────────────

def student_login(request):
    if request.method == "POST":
        enrollment = request.POST.get("enrollment_number", "").strip()
        pin = request.POST.get("pin_code", "").strip()
        student = Student.objects.filter(enrollment_number=enrollment).first()
        if not student:
            return render(request, 'core/login.html', {
                'error': 'No student found with that enrollment number.',
                'face_recognition_available': FACE_RECOGNITION_AVAILABLE
            })
        if student.pin_code and student.pin_code != pin:
            return render(request, 'core/login.html', {
                'error': 'Invalid PIN code. Please enter your 4-digit PIN.',
                'face_recognition_available': FACE_RECOGNITION_AVAILABLE
            })
        request.session['student_enrollment'] = enrollment
        return redirect('dashboard', enrollment_number=enrollment)
    return render(request, 'core/login.html', {'face_recognition_available': FACE_RECOGNITION_AVAILABLE})


@csrf_exempt
def face_login_api(request):
    """Receives a base64 webcam frame, runs face recognition, marks attendance."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST only'}, status=405)

    if not FACE_RECOGNITION_AVAILABLE:
        return JsonResponse({'status': 'error', 'message': 'Face recognition module not available.'}, status=503)

    try:
        data = json.loads(request.body)
        b64_image = data.get('image', '')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)

    enrollment, distance = recognize_face_from_b64(b64_image)

    if enrollment is None:
        return JsonResponse({'status': 'no_match', 'message': 'No face recognised. Hold still and try again.'})

    try:
        student = Student.objects.get(enrollment_number=enrollment)
    except Student.DoesNotExist:
        return JsonResponse({'status': 'no_match', 'message': f'Face matched enrollment {enrollment} but student not found in database.'})

    # Mark attendance for today
    from datetime import date
    record, created = AttendanceRecord.objects.get_or_create(
        student=student,
        date=date.today(),
        defaults={'status': 'Present'}
    )

    # Set session so the student is logged in
    request.session['student_enrollment'] = enrollment

    return JsonResponse({
        'status': 'matched',
        'name': student.name,
        'enrollment': enrollment,
        'attendance_marked': created,
        'distance': round(float(distance), 3) if distance is not None else None,
        'redirect_url': f'/dashboard/{enrollment}/'
    })


def student_logout(request):
    request.session.flush()
    return redirect('home')


def dashboard(request, enrollment_number):
    if request.session.get('student_enrollment') != enrollment_number:
        return redirect('student_login')
    student = get_object_or_404(Student, enrollment_number=enrollment_number)
    recent_records = AttendanceRecord.objects.filter(student=student).order_by('-date')[:10]
    leave_history = LeaveApplication.objects.filter(student=student).order_by('-date_requested')[:5]
    context = {
        'student': student,
        'records': recent_records,
        'leave_history': leave_history,
        'percentage': student.attendance_percentage,
    }
    return render(request, 'core/dashboard.html', context)


def apply_leave(request, enrollment_number):
    if request.session.get('student_enrollment') != enrollment_number:
        return redirect('student_login')
    student = get_object_or_404(Student, enrollment_number=enrollment_number)
    if request.method == "POST":
        date = request.POST.get("date_requested")
        reason = request.POST.get("reason", "").strip()
        if not date or not reason:
            messages.error(request, "Both date and reason are required.")
            return render(request, 'core/apply_leave.html', {'student': student})
        # FIX: Prevent duplicate leave applications for the same date.
        if LeaveApplication.objects.filter(student=student, date_requested=date).exists():
            messages.warning(request, "You have already submitted a leave application for that date.")
            return redirect('dashboard', enrollment_number=enrollment_number)
        LeaveApplication.objects.create(student=student, date_requested=date, reason=reason)
        messages.success(request, "Leave application submitted successfully.")
        return redirect('dashboard', enrollment_number=enrollment_number)
    return render(request, 'core/apply_leave.html', {'student': student})


# ─────────────────────────────────────────────
#  FACULTY REGISTRATION FLOW
# ─────────────────────────────────────────────

def faculty_register(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        username   = request.POST.get("username", "").strip()
        email      = request.POST.get("email", "").strip()
        department = request.POST.get("department", "").strip()
        phone      = request.POST.get("phone", "").strip()
        password   = request.POST.get("password", "")
        password2  = request.POST.get("password2", "")

        errors = {}
        if password != password2:
            errors['password'] = "Passwords do not match."
        if User.objects.filter(username=username).exists():
            errors['username'] = "That username is already taken."
        if User.objects.filter(email=email).exists():
            errors['email'] = "An account with that email already exists."

        if errors:
            return render(request, 'core/faculty_register.html', {'errors': errors, 'form': request.POST})

        # Create user as INACTIVE until approved
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name,
            is_active=False, is_staff=False
        )
        FacultyProfile.objects.create(user=user, department=department, phone=phone)
        return redirect('faculty_pending')

    return render(request, 'core/faculty_register.html')


def faculty_pending(request):
    return render(request, 'core/faculty_pending.html')


# ─────────────────────────────────────────────
#  FACULTY LOGIN / LOGOUT
# ─────────────────────────────────────────────

def faculty_login(request):
    if is_approved_faculty(request.user):
        return redirect('faculty_dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is None:
            return render(request, 'core/faculty_login.html', {'error': 'Invalid username or password.'})

        if not hasattr(user, 'faculty_profile'):
            return render(request, 'core/faculty_login.html', {'error': 'No faculty profile found. Please register first.'})

        if not user.faculty_profile.is_approved:
            return render(request, 'core/faculty_login.html', {
                'error': 'Your registration is awaiting approval by the Django administrator.',
                'show_pending_link': True
            })

        login(request, user)
        return redirect('faculty_dashboard')

    return render(request, 'core/faculty_login.html')


def faculty_logout(request):
    logout(request)
    return redirect('faculty_login')


# ─────────────────────────────────────────────
#  FACULTY DASHBOARD
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def faculty_dashboard(request):
    # FIX: Superuser may have no faculty_profile — auto-create to prevent crash.
    profile = getattr(request.user, 'faculty_profile', None)
    if profile is None:
        profile, _ = FacultyProfile.objects.get_or_create(
            user=request.user,
            defaults={'department': 'Administration', 'is_approved': True}
        )

    # FIX: Use annotate() so attendance_percentage is computed in ONE query,
    # not 2 queries per student (the old N+1 bug).
    students = Student.objects.annotate(
        total_classes=Count('attendancerecord', distinct=True),
        present_count=Count(
            'attendancerecord',
            filter=Q(attendancerecord__status='Present'),
            distinct=True
        ),
        excused_count=Count(
            'attendancerecord',
            filter=Q(attendancerecord__status='Excused'),
            distinct=True
        )
    ).order_by('name')

    recent_attendance = AttendanceRecord.objects.select_related('student').order_by('-date', '-time')[:60]
    pending_leaves = LeaveApplication.objects.filter(status='Pending').select_related('student')
    # FIX: include reviewed_by__user to avoid extra queries in template
    all_leaves = LeaveApplication.objects.select_related(
        'student', 'reviewed_by__user'
    ).order_by('-date_requested')[:20]

    alert_config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)

    threshold = alert_config.alert_threshold
    total_students = students.count()
    low_attendance_count = sum(
        1 for s in students
        if (s.total_classes - s.excused_count) == 0 or (s.present_count / max(1, (s.total_classes - s.excused_count)) * 100) < threshold
    )
    pending_count = pending_leaves.count()

    # ── New: RPA Bot audit logs (most recent 20) ──────────────────────────────
    bot_logs = RPABotLog.objects.select_related('triggered_by').order_by('-started_at')[:20]

    # ── New: Holiday count for dashboard badge ────────────────────────────────
    from datetime import date as date_cls
    holiday_count = HolidayCalendar.objects.filter(date__gte=date_cls.today()).count()

    context = {
        'profile': profile,
        'faculty_name': request.user.get_full_name() or request.user.username,
        'students': students,
        'recent_attendance': recent_attendance,
        'pending_leaves': pending_leaves,
        'all_leaves': all_leaves,
        'alert_config': alert_config,
        'total_students': total_students,
        'low_attendance_count': low_attendance_count,
        'pending_count': pending_count,
        'active_tab': request.GET.get('tab', 'students'),
        # New context for RPA Bots tab
        'bot_logs': bot_logs,
        'holiday_count': holiday_count,
    }
    return render(request, 'core/faculty_dashboard.html', context)


# ─────────────────────────────────────────────
#  STUDENT CRUD
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def add_student(request):
    if request.method == "POST":
        profile = getattr(request.user, 'faculty_profile', None)
        name       = request.POST.get("name", "").strip()
        enr        = request.POST.get("enrollment_number", "").strip()
        email      = request.POST.get("email", "").strip()
        p_email    = request.POST.get("parent_email", "").strip()
        p_phone    = request.POST.get("parent_phone", "").strip()
        department = request.POST.get("department", "").strip()
        year       = request.POST.get("year", 1)

        pin_code   = request.POST.get("pin_code", "").strip()
        photo      = request.FILES.get("student_photo")

        if not name or not enr:
            messages.error(request, "Student name and enrollment number are required.")
        elif Student.objects.filter(enrollment_number=enr).exists():
            messages.error(request, f"Enrollment number '{enr}' already exists.")
        else:
            face_enc_json = None
            if photo:
                try:
                    import face_recognition
                    import numpy as np
                    import cv2
                    img_bytes = photo.read()
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        encodings = face_recognition.face_encodings(rgb_img)
                        if encodings:
                            face_enc_json = json.dumps(encodings[0].tolist())
                            # Save copy to known_faces/<enrollment>.jpg
                            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                            faces_dir = os.path.join(base_dir, 'face_recognition', 'known_faces')
                            os.makedirs(faces_dir, exist_ok=True)
                            cv2.imwrite(os.path.join(faces_dir, f"{enr}.jpg"), img)
                        else:
                            messages.warning(request, f"Student added, but no face was detected in the photo.")
                except Exception as e:
                    messages.warning(request, f"Student added, but could not process photo: {e}")

            Student.objects.create(
                name=name, enrollment_number=enr, email=email,
                parent_email=p_email, parent_phone=p_phone,
                department=department, year=year, added_by=profile,
                pin_code=pin_code, face_encoding=face_enc_json
            )
            success_msg = f"Student '{name}' added successfully."
            if face_enc_json:
                success_msg += " Face recognition biometric profile enrolled!"
            messages.success(request, success_msg)

            # Invalidate face cache so the new student can immediately scan
            try:
                from face_login import invalidate_cache
                invalidate_cache()
            except ImportError:
                pass
    return redirect('/faculty/dashboard/?tab=students')


@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def delete_student(request, student_id):
    if request.method == "POST":
        student = get_object_or_404(Student, id=student_id)
        name = student.name
        student.delete()
        messages.success(request, f"Student '{name}' and all their records have been deleted.")
    return redirect('/faculty/dashboard/?tab=students')


# ─────────────────────────────────────────────
#  LEAVE MANAGEMENT
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def manage_leave(request, leave_id, action):
    # FIX: Reject GET requests — approving/rejecting must be an intentional POST.
    if request.method != 'POST':
        return redirect('/faculty/dashboard/?tab=leaves')
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    profile = getattr(request.user, 'faculty_profile', None)
    if action == 'approve':
        leave.status = 'Approved'
        leave.reviewed_by = profile
        leave.reviewed_at = timezone.now()
        leave.save()
        # Automatically update or create an attendance record with status='Excused'
        AttendanceRecord.objects.update_or_create(
            student=leave.student,
            date=leave.date_requested,
            defaults={'status': 'Excused'}
        )
        messages.success(request, f"Leave for {leave.student.name} approved and attendance recorded as Excused.")
    elif action == 'reject':
        leave.status = 'Rejected'
        leave.reviewed_by = profile
        leave.reviewed_at = timezone.now()
        leave.save()
        # If an Excused record was previously generated, revert it to Absent
        AttendanceRecord.objects.filter(
            student=leave.student,
            date=leave.date_requested,
            status='Excused'
        ).update(status='Absent')
        messages.warning(request, f"Leave for {leave.student.name} rejected.")
    else:
        messages.error(request, "Invalid leave action.")
        return redirect('/faculty/dashboard/?tab=leaves')
    return redirect('/faculty/dashboard/?tab=leaves')


# ─────────────────────────────────────────────
#  ALERT CONFIGURATION
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def save_alert_config(request):
    if request.method == "POST":
        profile = getattr(request.user, 'faculty_profile', None)
        if profile is None:
            messages.error(request, "No faculty profile found.")
            return redirect('/faculty/dashboard/?tab=alerts')
        config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)
        config.gmail_address       = request.POST.get("gmail_address", "").strip()
        
        gmail_pass = request.POST.get("gmail_app_password", "").strip()
        if gmail_pass and not gmail_pass.startswith('•'):
            config.set_encrypted_gmail_password(gmail_pass)

        raw_threshold = request.POST.get("alert_threshold", "75")
        config.alert_threshold     = max(0, min(100, int(raw_threshold) if raw_threshold.isdigit() else 75))
        config.email_alerts_enabled = request.POST.get("email_alerts_enabled") == "on"
        config.alert_email_subject = request.POST.get("alert_email_subject", "").strip()
        config.alert_email_body    = request.POST.get("alert_email_body", "").strip()

        # SMS settings
        config.twilio_account_sid  = request.POST.get("twilio_account_sid", "").strip()
        twilio_tok = request.POST.get("twilio_auth_token", "").strip()
        if twilio_tok and not twilio_tok.startswith('•'):
            config.set_encrypted_twilio_token(twilio_tok)

        config.twilio_from_number  = request.POST.get("twilio_from_number", "").strip()
        config.sms_alerts_enabled  = request.POST.get("sms_alerts_enabled") == "on"
        config.sms_alert_body      = request.POST.get("sms_alert_body", "").strip()

        # ── NEW: Bot 2 & 5 config ──────────────────────────────────────────────
        dean_email = request.POST.get("dean_email", "").strip()
        if dean_email:
            config.dean_email = dean_email

        raw_hod_threshold = request.POST.get("hod_report_threshold", "").strip()
        if raw_hod_threshold.isdigit():
            config.hod_report_threshold = max(0, min(100, int(raw_hod_threshold)))

        config.save()
        messages.success(request, "Alert configuration saved securely.")
    return redirect('/faculty/dashboard/?tab=alerts')


@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_alert_bot(request):
    """Sends attendance alerts directly via Python (smtplib + Twilio).

    Uses the module-level 'logger' (configured in settings.py LOGGING)
    so logs go to /tmp/rpa_debug.log AND the console.
    """
    import traceback

    if request.method != "POST":
        return redirect('/faculty/dashboard/?tab=alerts')

    try:
        logger.info("=== RUN ALERT BOT STARTED ===")
        logger.info("User: %s", request.user.username)

        # FIX: Use getattr to prevent crash when superuser has no faculty_profile
        profile = getattr(request.user, 'faculty_profile', None)
        if profile is None:
            messages.error(request, "No faculty profile found. Cannot run alert bot.")
            return redirect('/faculty/dashboard/?tab=alerts')

        config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)
        logger.info("Config: gmail=%r, sms_enabled=%s, threshold=%s",
                    config.gmail_address, config.sms_alerts_enabled, config.alert_threshold)

        gmail_password = config.get_decrypted_gmail_password()
        if not config.gmail_address or not gmail_password:
            logger.error("Gmail credentials missing")
            messages.error(request, "Gmail credentials not configured. Set them in Alert Configuration first.")
            return redirect('/faculty/dashboard/?tab=alerts')

        # FIX: Use annotate() to compute attendance in a single query — no N+1 here.
        threshold = config.alert_threshold
        all_students = list(Student.objects.annotate(
            total_classes=Count('attendancerecord', distinct=True),
            present_count=Count(
                'attendancerecord',
                filter=Q(attendancerecord__status='Present'),
                distinct=True
            ),
            excused_count=Count(
                'attendancerecord',
                filter=Q(attendancerecord__status='Excused'),
                distinct=True
            )
        ))
        low_students = [
            s for s in all_students
            if (s.total_classes - s.excused_count) == 0 or (s.present_count / max(1, (s.total_classes - s.excused_count)) * 100) < threshold
        ]
        logger.info("Students: total=%d, below threshold=%d", len(all_students), len(low_students))

        if not low_students:
            messages.warning(request, f"✅ All students are above {threshold}% — no alerts needed.")
            return redirect('/faculty/dashboard/?tab=alerts')

        # ── Gmail SMTP ──────────────────────────────────────────────────────────
        smtp_server = None
        email_errors = []
        email_sent = 0
        try:
            logger.info("Connecting Gmail SMTP...")
            smtp_server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
            smtp_server.starttls()
            smtp_server.login(config.gmail_address, gmail_password)
            logger.info("Gmail connected OK")
        except Exception as e:
            logger.error("Gmail SMTP failed: %s", e)
            email_errors.append(f"Gmail failed: {e}")

        # ── Twilio ──────────────────────────────────────────────────────────────
        twilio_client = None
        sms_errors = []
        sms_sent = 0
        twilio_token = config.get_decrypted_twilio_token()
        if config.sms_alerts_enabled and config.twilio_account_sid and twilio_token:
            try:
                from twilio.rest import Client as TwilioClient
                twilio_client = TwilioClient(config.twilio_account_sid, twilio_token)
                logger.info("Twilio client OK")
            except Exception as e:
                logger.error("Twilio failed: %s", e)
                sms_errors.append(f"Twilio: {e}")
            except Exception as e:
                logger.error("Twilio failed: %s", e)
                sms_errors.append(f"Twilio: {e}")

        # ── Send per-student alerts ─────────────────────────────────────────────
        for student in low_students:
            # Compute pct from annotations taking into account excused records
            countable = student.total_classes - student.excused_count
            pct = (
                round(student.present_count / countable * 100, 2)
                if countable > 0 else 0.0
            )
            name = student.name
            logger.info("Alerting: %s (%s%%)", name, pct)

            try:
                body = config.alert_email_body.format(
                    student_name=name, attendance_percentage=pct, threshold=threshold)
            except Exception:
                body = (f"Dear Parent/Guardian,\n\n{name} has {pct}% attendance "
                        f"(below {threshold}%). Please contact administration.\n\nRegards,\nUniversity")

            if smtp_server:
                try:
                    msg = EmailMessage()
                    msg['Subject'] = f"URGENT: Low Attendance Warning — {name}"
                    msg['From'] = config.gmail_address
                    msg['To'] = student.parent_email
                    msg.set_content(body)
                    smtp_server.send_message(msg)
                    email_sent += 1
                    logger.info("  ✉ Email sent → %s", student.parent_email)
                except Exception as e:
                    logger.error("  ✉ Email FAILED → %s: %s", student.parent_email, e)
                    email_errors.append(f"Email to {student.parent_email}: {e}")

            if twilio_client and student.parent_phone:
                try:
                    phone = student.parent_phone.strip()
                    if not phone.startswith('+'):
                        phone = '+91' + phone
                    try:
                        sms_body = config.sms_alert_body.format(
                            student_name=name, attendance_percentage=pct, threshold=threshold)
                    except Exception:
                        sms_body = f"URGENT: {name} has {pct}% attendance (below {threshold}%). Contact admin."
                    twilio_client.messages.create(
                        body=sms_body, from_=config.twilio_from_number, to=phone)
                    sms_sent += 1
                    logger.info("  📱 SMS sent → %s", phone)
                except Exception as e:
                    logger.error("  📱 SMS FAILED → %s: %s", student.parent_phone, e)
                    sms_errors.append(f"SMS to {student.parent_phone}: {e}")

        if smtp_server:
            try:
                smtp_server.quit()
            except Exception:
                pass

        config.last_run_at = timezone.now()
        config.save()
        logger.info("Done: emails=%d, sms=%d", email_sent, sms_sent)

        summary = (f"📊 Scanned {len(all_students)} students — "
                   f"{len(low_students)} below {threshold}%. "
                   f"📧 {email_sent} email(s) sent.")
        if config.sms_alerts_enabled:
            summary += f" 📱 {sms_sent} SMS sent."

        if email_errors or sms_errors:
            all_errors = email_errors + sms_errors
            messages.warning(request, f"{summary} | ⚠️ Errors: {' | '.join(all_errors[:3])}")
        else:
            messages.success(request, f"✅ {summary}")

    except Exception as e:
        tb = traceback.format_exc()
        logger.critical("UNCAUGHT EXCEPTION:\n%s", tb)
        messages.error(request, f"❌ Error: {e}")

    return redirect('/faculty/dashboard/?tab=alerts')
