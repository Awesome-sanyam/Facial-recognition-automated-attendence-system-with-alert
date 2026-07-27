from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess, os, sys, json, smtplib, threading
from email.message import EmailMessage

# Add face_recognition module to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'face_recognition'))
try:
    from face_login import recognize_face_from_b64
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

from .models import (
    FacultyProfile, AlertConfiguration,
    Student, AttendanceRecord, LeaveApplication
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
        if Student.objects.filter(enrollment_number=enrollment).exists():
            request.session['student_enrollment'] = enrollment
            return redirect('dashboard', enrollment_number=enrollment)
        return render(request, 'core/login.html', {'error': 'No student found with that enrollment number.'})
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
        reason = request.POST.get("reason")
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
    profile = request.user.faculty_profile
    students = Student.objects.all().order_by('name')
    recent_attendance = AttendanceRecord.objects.select_related('student').order_by('-date', '-time')[:60]
    pending_leaves = LeaveApplication.objects.filter(status='Pending').select_related('student')
    all_leaves = LeaveApplication.objects.select_related('student').order_by('-date_requested')[:20]

    alert_config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)

    # Stats
    total_students = students.count()
    low_attendance_count = sum(1 for s in students if s.attendance_percentage < alert_config.alert_threshold)
    pending_count = pending_leaves.count()

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
    }
    return render(request, 'core/faculty_dashboard.html', context)


# ─────────────────────────────────────────────
#  STUDENT CRUD
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def add_student(request):
    if request.method == "POST":
        profile = request.user.faculty_profile
        name       = request.POST.get("name", "").strip()
        enr        = request.POST.get("enrollment_number", "").strip()
        email      = request.POST.get("email", "").strip()
        p_email    = request.POST.get("parent_email", "").strip()
        p_phone    = request.POST.get("parent_phone", "").strip()
        department = request.POST.get("department", "").strip()
        year       = request.POST.get("year", 1)

        if Student.objects.filter(enrollment_number=enr).exists():
            messages.error(request, f"Enrollment number '{enr}' already exists.")
        else:
            Student.objects.create(
                name=name, enrollment_number=enr, email=email,
                parent_email=p_email, parent_phone=p_phone,
                department=department, year=year, added_by=profile
            )
            messages.success(request, f"Student '{name}' added successfully.")
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
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    profile = request.user.faculty_profile
    if action == 'approve':
        leave.status = 'Approved'
        leave.reviewed_by = profile
        leave.reviewed_at = timezone.now()
        messages.success(request, f"Leave for {leave.student.name} approved.")
    elif action == 'reject':
        leave.status = 'Rejected'
        leave.reviewed_by = profile
        leave.reviewed_at = timezone.now()
        messages.warning(request, f"Leave for {leave.student.name} rejected.")
    leave.save()
    return redirect('/faculty/dashboard/?tab=leaves')


# ─────────────────────────────────────────────
#  ALERT CONFIGURATION
# ─────────────────────────────────────────────

@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def save_alert_config(request):
    if request.method == "POST":
        profile = request.user.faculty_profile
        config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)
        config.gmail_address       = request.POST.get("gmail_address", "").strip()
        config.gmail_app_password  = request.POST.get("gmail_app_password", "").strip()
        config.alert_threshold     = int(request.POST.get("alert_threshold", 75))
        config.email_alerts_enabled = request.POST.get("email_alerts_enabled") == "on"
        config.alert_email_subject = request.POST.get("alert_email_subject", "").strip()
        config.alert_email_body    = request.POST.get("alert_email_body", "").strip()
        
        # SMS settings
        config.twilio_account_sid  = request.POST.get("twilio_account_sid", "").strip()
        config.twilio_auth_token   = request.POST.get("twilio_auth_token", "").strip()
        config.twilio_from_number  = request.POST.get("twilio_from_number", "").strip()
        config.sms_alerts_enabled  = request.POST.get("sms_alerts_enabled") == "on"
        config.sms_alert_body      = request.POST.get("sms_alert_body", "").strip()
        
        config.save()

        # Write settings into the Robot Framework tasks.robot
        _update_robot_config(config)
        messages.success(request, "Alert configuration saved and applied to the RPA bot.")
    return redirect('/faculty/dashboard/?tab=alerts')


def _update_robot_config(config):
    """Rewrites the Robot Framework tasks.robot variables to match the DB config."""
    robot_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'rpa_bot', 'tasks.robot'
    )
    if not os.path.exists(robot_path):
        return
    with open(robot_path, 'r') as f:
        content = f.read()

    import re
    # Email Variables
    if config.gmail_address:
        content = re.sub(r'(?m)^(\$\{GMAIL_USER\})[ \t]+\S+', rf'\1     {config.gmail_address}', content)
    if config.gmail_app_password:
        content = re.sub(r'(?m)^(\$\{GMAIL_PASS\})[ \t]+\S+', rf'\1     {config.gmail_app_password}', content)
    
    # Twilio Variables — always overwrite to keep in sync
    content = re.sub(r'(?m)^(\$\{TWILIO_SID\})[ \t]+.*', rf'\1     {config.twilio_account_sid}', content)
    content = re.sub(r'(?m)^(\$\{TWILIO_TOKEN\})[ \t]+.*', rf'\1     {config.twilio_auth_token}', content)
    content = re.sub(r'(?m)^(\$\{TWILIO_FROM\})[ \t]+.*', rf'\1     {config.twilio_from_number}', content)
    content = re.sub(r'(?m)^(\$\{SMS_ENABLED\})[ \t]+.*', rf'\1     {str(config.sms_alerts_enabled)}', content)

    with open(robot_path, 'w') as f:
        f.write(content)


@user_passes_test(is_approved_faculty, login_url='/faculty/login/')
def run_alert_bot(request):
    """Sends attendance alerts directly via Python (smtplib + Twilio)."""
    import traceback, logging

    log_path = '/tmp/rpa_debug.log'
    logging.basicConfig(filename=log_path, level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s', filemode='w')
    log = logging.getLogger('rpa_bot')

    if request.method != "POST":
        return redirect('/faculty/dashboard/?tab=alerts')

    try:
        log.info("=== RUN ALERT BOT STARTED ===")
        log.info(f"User: {request.user.username}")

        profile = request.user.faculty_profile
        config, _ = AlertConfiguration.objects.get_or_create(faculty=profile)
        log.info(f"Config: gmail={config.gmail_address!r}, sms_enabled={config.sms_alerts_enabled}, threshold={config.alert_threshold}")

        if not config.gmail_address or not config.gmail_app_password:
            log.error("Gmail credentials missing")
            messages.error(request, "Gmail credentials not configured. Set them in Alert Configuration first.")
            return redirect('/faculty/dashboard/?tab=alerts')

        all_students = list(Student.objects.all())
        threshold = config.alert_threshold
        low_students = [s for s in all_students if s.attendance_percentage < threshold]
        log.info(f"Students: total={len(all_students)}, below threshold={len(low_students)}")

        if not low_students:
            messages.warning(request, f"All students above {threshold}% — no alerts needed.")
            return redirect('/faculty/dashboard/?tab=alerts')

        # Gmail SMTP
        smtp_server = None
        email_errors = []
        email_sent = 0
        try:
            log.info("Connecting Gmail SMTP...")
            smtp_server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
            smtp_server.starttls()
            smtp_server.login(config.gmail_address, config.gmail_app_password)
            log.info("Gmail connected OK")
        except Exception as e:
            log.error(f"Gmail SMTP failed: {e}")
            email_errors.append(f"Gmail failed: {str(e)}")

        # Twilio
        twilio_client = None
        sms_errors = []
        sms_sent = 0
        if config.sms_alerts_enabled and config.twilio_account_sid and config.twilio_auth_token:
            try:
                from twilio.rest import Client as TwilioClient
                twilio_client = TwilioClient(config.twilio_account_sid, config.twilio_auth_token)
                log.info("Twilio connected OK")
            except Exception as e:
                log.error(f"Twilio failed: {e}")
                sms_errors.append(f"Twilio failed: {str(e)}")

        # Send per student
        for student in low_students:
            pct = student.attendance_percentage
            name = student.name
            log.info(f"Student: {name} ({pct}%)")

            try:
                body = config.alert_email_body.format(
                    student_name=name, attendance_percentage=pct, threshold=threshold)
            except Exception:
                body = (f"Dear Parent/Guardian,\n\n{name} has {pct}% attendance "
                        f"(below {threshold}% threshold). Contact administration.\n\nRegards,\nUniversity")

            if smtp_server:
                try:
                    msg = EmailMessage()
                    msg['Subject'] = f"URGENT: Low Attendance Warning — {name}"
                    msg['From'] = config.gmail_address
                    msg['To'] = student.parent_email
                    msg.set_content(body)
                    smtp_server.send_message(msg)
                    email_sent += 1
                    log.info(f"  Email sent -> {student.parent_email}")
                except Exception as e:
                    log.error(f"  Email failed -> {student.parent_email}: {e}")
                    email_errors.append(f"Email to {student.parent_email}: {str(e)}")

            if twilio_client and student.parent_phone:
                try:
                    phone = student.parent_phone.strip()
                    if not phone.startswith('+'):
                        phone = '+91' + phone
                    try:
                        sms_body = config.sms_alert_body.format(
                            student_name=name, attendance_percentage=pct, threshold=threshold)
                    except Exception:
                        sms_body = f"URGENT: {name} has {pct}% attendance (below {threshold}%). Contact administration."

                    twilio_client.messages.create(
                        body=sms_body, from_=config.twilio_from_number, to=phone)
                    sms_sent += 1
                    log.info(f"  SMS sent -> {phone}")
                except Exception as e:
                    log.error(f"  SMS failed -> {student.parent_phone}: {e}")
                    sms_errors.append(f"SMS to {student.parent_phone}: {str(e)}")

        if smtp_server:
            try:
                smtp_server.quit()
            except Exception:
                pass

        config.last_run_at = timezone.now()
        config.save()
        log.info(f"Done: emails={email_sent}, sms={sms_sent}, email_errors={email_errors}, sms_errors={sms_errors}")

        summary = (f"Scanned {len(all_students)} students — {len(low_students)} below {threshold}%. "
                   f"{email_sent} email(s) sent.")
        if config.sms_alerts_enabled:
            summary += f" {sms_sent} SMS sent."

        if email_errors or sms_errors:
            all_errors = email_errors + sms_errors
            messages.warning(request, f"{summary} | Errors: {' | '.join(all_errors[:3])}")
        else:
            messages.success(request, f"SUCCESS: {summary}")

    except Exception as e:
        tb = traceback.format_exc()
        log.critical(f"UNCAUGHT EXCEPTION:\n{tb}")
        messages.error(request, f"Error: {str(e)}")

    return redirect('/faculty/dashboard/?tab=alerts')

