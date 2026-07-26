from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Student, AttendanceRecord, LeaveApplication


# ─────────────────────────────────────────────
#  STUDENT PORTAL VIEWS
# ─────────────────────────────────────────────

def home(request):
    """Landing page — lets user choose Student or Faculty login."""
    return render(request, 'core/home.html')


def student_login(request):
    if request.method == "POST":
        enrollment = request.POST.get("enrollment_number", "").strip()
        if Student.objects.filter(enrollment_number=enrollment).exists():
            # Store enrollment in session so the student stays logged in
            request.session['student_enrollment'] = enrollment
            return redirect('dashboard', enrollment_number=enrollment)
        else:
            return render(request, 'core/login.html', {'error': 'No student found with that enrollment number.'})
    return render(request, 'core/login.html')


def student_logout(request):
    request.session.flush()
    return redirect('home')


def dashboard(request, enrollment_number):
    # Ensure the session matches (basic access control)
    if request.session.get('student_enrollment') != enrollment_number:
        return redirect('student_login')
    student = get_object_or_404(Student, enrollment_number=enrollment_number)
    recent_records = AttendanceRecord.objects.filter(student=student).order_by('-date')[:10]
    context = {
        'student': student,
        'records': recent_records,
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
#  FACULTY PORTAL VIEWS
# ─────────────────────────────────────────────

def is_faculty(user):
    return user.is_authenticated and user.is_staff


def faculty_login(request):
    """Custom faculty login view using Django auth."""
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('faculty_dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('faculty_dashboard')
        else:
            return render(request, 'core/faculty_login.html', {
                'error': 'Invalid credentials or you are not authorised as Faculty.'
            })
    return render(request, 'core/faculty_login.html')


def faculty_logout(request):
    logout(request)
    return redirect('faculty_login')


@user_passes_test(is_faculty, login_url='/faculty/login/')
def faculty_dashboard(request):
    students = Student.objects.all().order_by('name')
    recent_attendance = AttendanceRecord.objects.select_related('student').order_by('-date', '-time')[:60]
    pending_leaves = LeaveApplication.objects.filter(status='Pending').select_related('student')
    approved_leaves = LeaveApplication.objects.filter(status='Approved').select_related('student').order_by('-date_requested')[:10]

    # Summary stats
    total_students = students.count()
    low_attendance_count = sum(1 for s in students if s.attendance_percentage < 75)
    pending_count = pending_leaves.count()

    context = {
        'students': students,
        'recent_attendance': recent_attendance,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'total_students': total_students,
        'low_attendance_count': low_attendance_count,
        'pending_count': pending_count,
        'faculty_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'core/faculty_dashboard.html', context)


@user_passes_test(is_faculty, login_url='/faculty/login/')
def manage_leave(request, leave_id, action):
    leave = get_object_or_404(LeaveApplication, id=leave_id)
    if action == 'approve':
        leave.status = 'Approved'
        messages.success(request, f"Leave for {leave.student.name} approved.")
    elif action == 'reject':
        leave.status = 'Rejected'
        messages.warning(request, f"Leave for {leave.student.name} rejected.")
    leave.save()
    return redirect('faculty_dashboard')