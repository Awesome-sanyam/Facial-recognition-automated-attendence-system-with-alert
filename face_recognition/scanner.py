"""
scanner.py — High-performance classroom facial recognition attendance scanner.

Optimizations:
1. Loads 128-d face embeddings from Django DB (Student.face_encoding) + known_faces/.
2. Frame-skipping: detects and encodes faces on 1 of every 3 frames, keeping UI at 30+ FPS.
3. In-memory cache: maintains `marked_today_enrollments` set to eliminate redundant SQLite queries.

Stability fixes (v2):
4. try/finally guarantees camera release even on exceptions.
5. Consecutive-failure counter exits cleanly when camera disconnects.
6. DB writes isolated in a retry helper to avoid SQLite lock collisions with Django.
"""

import cv2
import face_recognition
import numpy as np
import os
import sys
import json
import time
import logging
import django
from datetime import datetime

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    filename='/tmp/scanner_errors.log',
    level=logging.ERROR,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# --- Django Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web_app')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_system.settings")
django.setup()

from django.db import OperationalError
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


# ── Retry helper: isolates DB writes to avoid SQLite lock on concurrent Django ──
def _mark_present_with_retry(enrollment, max_retries=3, delay=0.4):
    """Write an AttendanceRecord with retry on SQLite lock. Returns student name or None."""
    for attempt in range(1, max_retries + 1):
        try:
            student = Student.objects.get(enrollment_number=enrollment)
            AttendanceRecord.objects.get_or_create(
                student=student,
                date=today,
                defaults={'status': 'Present', 'time': datetime.now().time()}
            )
            return student.name
        except OperationalError as e:
            if attempt < max_retries:
                time.sleep(delay)
            else:
                logging.error("DB lock after %d retries for %s: %s", max_retries, enrollment, e)
                return None
        except Student.DoesNotExist:
            logging.warning("Face matched enrollment %s but Student not in DB.", enrollment)
            return None
    return None


# ── Camera Initialization ──────────────────────────────────────────────────────
print("Starting camera... Press 'q' to quit.")
CAMERA_INDEX = 0
video_capture = cv2.VideoCapture(CAMERA_INDEX)

if not video_capture.isOpened():
    logging.error("cv2.VideoCapture(%d) failed to open.", CAMERA_INDEX)
    print("❌ FATAL: Camera not found or already in use (index %d)." % CAMERA_INDEX)
    raise SystemExit(1)

frame_count = 0
face_locations = []
face_labels = []
MAX_CONSECUTIVE_FAILURES = 30   # ~1 second at 30fps before giving up

consecutive_failures = 0

# ── Main Loop — wrapped in try/finally to GUARANTEE camera release ─────────────
try:
    while True:
        ret, frame = video_capture.read()

        if not ret:
            consecutive_failures += 1
            logging.warning("Frame read failure %d/%d", consecutive_failures, MAX_CONSECUTIVE_FAILURES)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print("❌ Camera stream lost after %d consecutive failures. Exiting." % MAX_CONSECUTIVE_FAILURES)
                break
            continue  # skip this frame, keep trying

        consecutive_failures = 0  # reset on good frame
        frame_count += 1

        # Process face recognition every 3rd frame to conserve CPU
        if frame_count % 3 == 0 and len(known_face_encodings) > 0:
            try:
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

                            if enrollment in marked_today_enrollments:
                                label = f"{student_name} (Present)"
                            else:
                                # Use retry helper — safe against SQLite DB lock
                                name = _mark_present_with_retry(enrollment)
                                if name:
                                    marked_today_enrollments.add(enrollment)
                                    label = f"{student_name} (Present)"
                                    print(f"✅ MARKED: {student_name} ({confidence}% match)")
                                else:
                                    label = f"{enrollment} (DB error)"

                    face_labels.append(label)

            except Exception as exc:
                # Never crash the loop on a recognition error — just log and skip
                logging.error("Face recognition error on frame %d: %s", frame_count, exc)
                face_labels = []

        # Render bounding boxes and labels
        for face_loc, label in zip(face_locations, face_labels):
            top, right, bottom, left = [coord * 2 for coord in face_loc]
            is_known = "Present" in label or ("(" in label and "Unknown" not in label and "error" not in label)
            color = (0, 255, 0) if is_known else (0, 0, 255)

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.rectangle(frame, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
            cv2.putText(frame, label, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

        cv2.imshow('Classroom Attendance Scanner', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print("\n⌨️  Scanner interrupted by user (Ctrl+C).")

except Exception as fatal:
    logging.exception("FATAL unhandled error in scanner main loop: %s", fatal)
    print(f"❌ Scanner crashed: {fatal}\nDetails logged to /tmp/scanner_errors.log")

finally:
    # ALWAYS executes: camera is released regardless of how we exit
    video_capture.release()
    cv2.destroyAllWindows()
    print("✅ Camera released. Attendance scanner shut down cleanly.")