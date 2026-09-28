"""
face_login.py — face_recognition API for web login and classroom scanning.

Algorithm:
1. Load face encodings directly from database (Student.face_encoding)
   and fallback to known_faces/ folder.
2. Receive base64 frame from web browser or OpenCV frame from camera.
3. Extract 128-d face embedding via dlib HOG.
4. Compute vectorized Euclidean distance against known encodings.
5. Return matching enrollment number if best distance < 0.6.
"""

import face_recognition
import numpy as np
import base64
import os
import sys
import json
import cv2
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWN_FACES_DIR = BASE_DIR / 'face_recognition' / 'known_faces'

_known_face_encodings = []
_known_face_enrollments = []
_is_loaded = False


def _get_django_student_model():
    """Safely get the Student model if Django is configured."""
    try:
        from django.apps import apps
        if apps.ready:
            return apps.get_model('core', 'Student')
    except Exception:
        pass
    return None


def _load_known_faces():
    """
    Load face encodings from Database (primary) and known_faces/ (fallback).
    Encodings are cached in memory for high-throughput sub-millisecond matching.
    """
    global _is_loaded, _known_face_encodings, _known_face_enrollments
    _known_face_encodings = []
    _known_face_enrollments = []

    loaded_enrollments = set()
    Student = _get_django_student_model()

    # 1. Load from Database
    if Student is not None:
        try:
            db_students = Student.objects.exclude(
                face_encoding__isnull=True
            ).exclude(face_encoding='')
            for s in db_students:
                try:
                    encoding_list = json.loads(s.face_encoding)
                    if isinstance(encoding_list, list) and len(encoding_list) == 128:
                        _known_face_encodings.append(np.array(encoding_list, dtype=np.float64))
                        _known_face_enrollments.append(s.enrollment_number)
                        loaded_enrollments.add(s.enrollment_number)
                except (json.JSONDecodeError, ValueError):
                    pass
        except Exception as e:
            print(f"[face_login] DB load notice: {e}")

    # 2. Fallback / Sync from known_faces/ filesystem
    if KNOWN_FACES_DIR.exists():
        for filename in os.listdir(KNOWN_FACES_DIR):
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                enrollment = os.path.splitext(filename)[0]
                if enrollment in loaded_enrollments:
                    continue  # Already loaded from database

                image_path = os.path.join(KNOWN_FACES_DIR, filename)
                try:
                    image = face_recognition.load_image_file(image_path)
                    encodings = face_recognition.face_encodings(image)
                    if encodings:
                        encoding = encodings[0]
                        _known_face_encodings.append(encoding)
                        _known_face_enrollments.append(enrollment)
                        loaded_enrollments.add(enrollment)

                        # Auto-persist to DB if Student exists
                        if Student is not None:
                            try:
                                student = Student.objects.filter(enrollment_number=enrollment).first()
                                if student and not student.face_encoding:
                                    student.face_encoding = json.dumps(encoding.tolist())
                                    student.save(update_fields=['face_encoding'])
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[face_login] Warning reading {filename}: {e}")

    _is_loaded = True
    return True


def recognize_face_from_b64(b64_image: str):
    """
    Takes a base64-encoded image string, returns (enrollment_number, distance).
    Distance is the Euclidean face distance (< 0.6 is a match).
    """
    global _is_loaded

    if not _is_loaded:
        _load_known_faces()

    if not _known_face_encodings:
        return None, None

    # Strip base64 header if present
    if ',' in b64_image:
        b64_image = b64_image.split(',')[1]

    try:
        img_bytes = base64.b64decode(b64_image)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    except Exception:
        return None, None

    if frame is None:
        return None, None

    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Downscale for faster face location detection
    small_rgb = cv2.resize(rgb_frame, (0, 0), fx=0.5, fy=0.5)
    small_locations = face_recognition.face_locations(small_rgb)
    if not small_locations:
        return None, None

    # Upscale locations back to original frame for encoding
    face_locations = [(top * 2, right * 2, bottom * 2, left * 2) for (top, right, bottom, left) in small_locations]
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    if not face_encodings:
        return None, None

    # Match primary face against all known face encodings
    face_encoding = face_encodings[0]
    face_distances = face_recognition.face_distance(_known_face_encodings, face_encoding)

    if len(face_distances) > 0:
        best_match_index = int(np.argmin(face_distances))
        best_distance = float(face_distances[best_match_index])

        # Strictness threshold (0.6 is industry standard for 128-d Euclidean)
        if best_distance < 0.6:
            enrollment = _known_face_enrollments[best_match_index]
            return enrollment, best_distance

    return None, None


def invalidate_cache():
    """Call this when a student is added, deleted, or photo updated to reload memory."""
    global _is_loaded
    _is_loaded = False
