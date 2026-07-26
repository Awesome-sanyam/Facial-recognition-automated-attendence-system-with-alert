from django.db import models

class Student(models.Model):
    name = models.CharField(max_length=100)
    enrollment_number = models.CharField(max_length=20, unique=True)
    parent_email = models.EmailField()
    parent_phone = models.CharField(max_length=15)
    face_encoding = models.TextField(blank=True, null=True) 

    @property
    def attendance_percentage(self):
        total_records = self.attendancerecord_set.count()
        if total_records == 0:
            return 0  # Prevents division by zero if no classes have happened
            
        present_count = self.attendancerecord_set.filter(status='Present').count()
        percentage = (present_count / total_records) * 100
        return round(percentage, 2)

    def __str__(self):
        return f"{self.name} ({self.enrollment_number})"

class AttendanceRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=[('Present', 'Present'), ('Absent', 'Absent')], default='Present')

    class Meta:
        # Ensures a student can't be marked present twice on the same day
        unique_together = ('student', 'date')

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.status}"

class LeaveApplication(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date_requested = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=15, 
        choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
        default='Pending'
    )

    def __str__(self):
        return f"Leave: {self.student.name} for {self.date_requested}"
