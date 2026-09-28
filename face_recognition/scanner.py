"""
scanner.py — High-performance classroom facial recognition attendance scanner.

Optimizations:
1. Loads 128-d face embeddings from Django DB (Student.face_encoding) + known_faces/.
2. Frame-skipping: detects and encodes faces on 1 of every 3 frames, keeping UI at 30+ FPS.
3. In-memory cache: maintains `marked_today_enrollments` set to eliminate redundant SQLite queries.
"""

import cv2
import face_recognition
import numpy as np
import os
import sys
import json
import django
from datetime import datetime

# --- Django Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web_app')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_system.settings")
django.setup()

from core.models import Student, AttendanceRecord

# --- Facial Recognition Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
known_face_encodings = []
known_face_enrollments = []
student_name_map = {}

print("Loading student biometric profiles...")

# 1. Load from Database
db_students = Student.objects.all()
for s in db_students:
    student_name_map[s.enrollment_number] = s.name
    if s.face_encoding:
        try:
            vec = json.loads(s.face_encoding)
            if isinstance(vec, list) and len(vec) == 128:
                known_face_encodings.append(np.array(vec, dtype=np.float64))
                known_face_enrollments.append(s.enrollment_number)
        except Exception:
            pass

# 2. Fallback to filesystem
if os.path.exists(KNOWN_FACES_DIR):
    for filename in os.listdir(KNOWN_FACES_DIR):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            enr = os.path.splitext(filename)[0]
            if enr in known_face_enrollments:
                continue
            image_path = os.path.join(KNOWN_FACES_DIR, filename)
            try:
                img = face_recognition.load_image_file(image_path)
                encs = face_recognition.face_encodings(img)
                if encs:
                    known_face_encodings.append(encs[0])
                    known_face_enrollments.append(enr)
                    s = Student.objects.filter(enrollment_number=enr).first()
                    if s:
                        student_name_map[enr] = s.name
            except Exception:
                pass

print(f"Loaded {len(known_face_encodings)} enrolled face profile(s).")

# In-memory cache for today's marked attendance
today = datetime.today().date()
marked_today_enrollments = set(
    AttendanceRecord.objects.filter(date=today, status='Present')
    .values_list('student__enrollment_number', flat=True)
)
print(f"Today's attendance cache: {len(marked_today_enrollments)} student(s) already marked present.")

print("Starting camera... Press 'q' to quit.")
video_capture = cv2.VideoCapture(0)

frame_count = 0
face_locations = []
face_labels = []

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    frame_count += 1

    # Process face recognition every 3rd frame to conserve CPU
    if frame_count % 3 == 0 and len(known_face_encodings) > 0:
        face_labels = []
        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for face_encoding in face_encodings:
            TOLERANCE = 0.6
            label = "Unknown"
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

            if len(face_distances) > 0:
                best_idx = int(face_distances.argmin())
                best_dist = float(face_distances[best_idx])

                if best_dist < TOLERANCE:
                    enrollment = known_face_enrollments[best_idx]
                    student_name = student_name_map.get(enrollment, enrollment)
                    confidence = round((1 - best_dist) * 100, 1)

                    # Check memory cache before querying SQLite
                    if enrollment in marked_today_enrollments:
                        label = f"{student_name} (Present)"
                    else:
                        try:
                            student = Student.objects.get(enrollment_number=enrollment)
                            record, created = AttendanceRecord.objects.get_or_create(
                                student=student,
                                date=today,
                                defaults={'status': 'Present'}
                            )
                            marked_today_enrollments.add(enrollment)
                            label = f"{student_name} (Present)"
                            print(f"✅ MARKED: {student.name} ({confidence}% match)")
                        except Student.DoesNotExist:
                            label = f"{enrollment} ({confidence}%)"

            face_labels.append(label)

    # Render bounding boxes and labels
    for face_loc, label in zip(face_locations, face_labels):
        top, right, bottom, left = [coord * 2 for coord in face_loc]
        is_known = "Present" in label or ("(" in label and "Unknown" not in label)
        color = (0, 255, 0) if is_known else (0, 0, 255)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, label, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

    cv2.imshow('Classroom Attendance Scanner', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()