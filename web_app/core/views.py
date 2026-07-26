from django.shortcuts import render, redirect, get_object_or_404
from .models import Student, AttendanceRecord, LeaveApplication

def student_login(request):
    if request.method == "POST":
        enrollment = request.POST.get("enrollment_number")
        # In a real app we'd use passwords, but for this academic project, 
        # logging in via enrollment number keeps the scope manageable.
        if Student.objects.filter(enrollment_number=enrollment).exists():
            return redirect('dashboard', enrollment_number=enrollment)
        else:
            return render(request, 'core/login.html', {'error': 'Student not found.'})
            
    return render(request, 'core/login.html')

def dashboard(request, enrollment_number):
    student = get_object_or_404(Student, enrollment_number=enrollment_number)
    # Fetch the 10 most recent attendance records
    recent_records = AttendanceRecord.objects.filter(student=student).order_by('-date')[:10]
    
    context = {
        'student': student,
        'records': recent_records,
        'percentage': student.attendance_percentage
    }
    return render(request, 'core/dashboard.html', context)

def apply_leave(request, enrollment_number):
    student = get_object_or_404(Student, enrollment_number=enrollment_number)
    
    if request.method == "POST":
        date = request.POST.get("date_requested")
        reason = request.POST.get("reason")
        LeaveApplication.objects.create(student=student, date_requested=date, reason=reason)
        return redirect('dashboard', enrollment_number=enrollment_number)
        
    return render(request, 'core/apply_leave.html', {'student': student})