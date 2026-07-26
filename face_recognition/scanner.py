import cv2
import face_recognition
import os
import sys
import django
from datetime import datetime

# --- Django Setup ---
# This allows the standalone script to use Django's database models directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web_app')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendance_system.settings")
django.setup()

from core.models import Student, AttendanceRecord

# --- Facial Recognition Setup ---
KNOWN_FACES_DIR = "known_faces"
known_face_encodings = []
known_face_enrollments = []

print("Loading known faces into memory...")
for filename in os.listdir(KNOWN_FACES_DIR):
    if filename.endswith(".jpg") or filename.endswith(".png"):
        image_path = os.path.join(KNOWN_FACES_DIR, filename)
        image = face_recognition.load_image_file(image_path)
        
        try:
            # Get the face encoding for the image
            encoding = face_recognition.face_encodings(image)[0]
            known_face_encodings.append(encoding)
            
            # Extract enrollment number from filename (e.g., ENR123456.jpg -> ENR123456)
            enrollment = os.path.splitext(filename)[0]
            known_face_enrollments.append(enrollment)
        except IndexError:
            print(f"Warning: No face found in {filename}")

print("Starting camera... Press 'q' to quit.")
video_capture = cv2.VideoCapture(0)

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # OPTIMIZATION: Resize frame to 1/4 size for faster face recognition processing.
    # This prevents the script from overloading system memory while running alongside other apps.
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Find all faces in the current frame
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        enrollment = "Unknown"

        if True in matches:
            first_match_index = matches.index(True)
            enrollment = known_face_enrollments[first_match_index]

            # --- Log Attendance in Django ---
            try:
                student = Student.objects.get(enrollment_number=enrollment)
                today = datetime.today().date()
                
                # Check if already marked present today
                record, created = AttendanceRecord.objects.get_or_create(
                    student=student,
                    date=today,
                    defaults={'status': 'Present'}
                )
                
                if created:
                    print(f"Success: Logged attendance for {student.name}")
                    
            except Student.DoesNotExist:
                print(f"Error: {enrollment} recognized, but not found in Database.")

        # Scale back up face locations to draw the box on the original frame
        top, right, bottom, left = [coord * 4 for coord in face_location]
        
        # Draw a box and label around the face
        cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
        cv2.putText(frame, enrollment, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.5, (255, 255, 255), 1)

    cv2.imshow('Classroom Attendance Scanner', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()