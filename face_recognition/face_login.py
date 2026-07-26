"""
face_login.py — face_recognition API for web login.

Algorithm:
1. Receive a base64-encoded JPEG frame from the browser
2. Decode it into an image array
3. Run face_recognition.face_encodings to extract face
4. Compare against stored face images in known_faces/
5. If match found, return student data
"""

import face_recognition
import numpy as np
import base64
import os
import cv2
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
KNOWN_FACES_DIR = BASE_DIR / 'face_recognition' / 'known_faces'

_known_face_encodings = []
_known_face_enrollments = []
_is_loaded = False


def _load_known_faces():
    """
    Load all images in known_faces/ and extract their encodings.
    Called lazily on first use.
    """
    global _is_loaded, _known_face_encodings, _known_face_enrollments
    _known_face_encodings = []
    _known_face_enrollments = []

    if not KNOWN_FACES_DIR.exists():
        return False

    for filename in os.listdir(KNOWN_FACES_DIR):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            image_path = os.path.join(KNOWN_FACES_DIR, filename)
            image = face_recognition.load_image_file(image_path)
            
            try:
                encoding = face_recognition.face_encodings(image)[0]
                _known_face_encodings.append(encoding)
                
                # Extract enrollment number from filename (e.g., ENR123456.jpg -> ENR123456)
                enrollment = os.path.splitext(filename)[0]
                _known_face_enrollments.append(enrollment)
            except IndexError:
                pass

    _is_loaded = True
    return True


def recognize_face_from_b64(b64_image: str):
    """
    Takes a base64-encoded image string, returns (enrollment_number, distance).
    Distance is the face distance (lower is better, typically < 0.6 is a match).
    """
    global _is_loaded

    if not _is_loaded:
        _load_known_faces()

    if not _known_face_encodings:
        return None, None

    # Decode base64
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

    # Convert BGR (OpenCV) to RGB (face_recognition)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Find faces in the frame
    face_locations = face_recognition.face_locations(rgb_frame)
    if not face_locations:
        return None, None
        
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    
    if not face_encodings:
        return None, None

    # Check the first detected face
    face_encoding = face_encodings[0]
    
    # Calculate face distance to all known faces
    face_distances = face_recognition.face_distance(_known_face_encodings, face_encoding)
    
    if len(face_distances) > 0:
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]
        
        # 0.6 is the default strictness threshold
        if best_distance < 0.6:
            enrollment = _known_face_enrollments[best_match_index]
            return enrollment, float(best_distance)

    return None, None


def invalidate_cache():
    """Call this after new face images are added to force re-loading."""
    global _is_loaded
    _is_loaded = False
