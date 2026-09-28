"""
sync_face_encodings.py — Management command to extract face encodings from
known_faces/ images and persist them into the Student model.

Usage:
  python manage.py sync_face_encodings
"""

import os
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from core.models import Student

try:
    import face_recognition
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False


class Command(BaseCommand):
    help = "Extract 128-d face embeddings from known_faces/ images and persist to Student database."

    def handle(self, *args, **options):
        if not FACE_REC_AVAILABLE:
            self.stderr.write(self.style.ERROR("face_recognition package is not installed."))
            return

        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
        known_faces_dir = base_dir / 'face_recognition' / 'known_faces'

        if not known_faces_dir.exists():
            self.stderr.write(self.style.ERROR(f"Directory {known_faces_dir} does not exist."))
            return

        synced = 0
        skipped = 0
        failed = 0

        for filename in os.listdir(known_faces_dir):
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            enrollment = os.path.splitext(filename)[0]
            student = Student.objects.filter(enrollment_number=enrollment).first()

            if not student:
                self.stdout.write(self.style.WARNING(f"Image {filename} found but no Student with enrollment {enrollment}."))
                skipped += 1
                continue

            image_path = os.path.join(known_faces_dir, filename)
            try:
                img = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(img)
                if not encodings:
                    self.stdout.write(self.style.WARNING(f"No face detected in {filename}."))
                    failed += 1
                    continue

                encoding_vector = encodings[0].tolist()
                student.face_encoding = json.dumps(encoding_vector)
                student.save(update_fields=['face_encoding'])
                synced += 1
                self.stdout.write(self.style.SUCCESS(f"Synced face encoding for {student.name} ({enrollment})."))

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error processing {filename}: {e}"))
                failed += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nSync complete!\n"
            f"   Synced  : {synced}\n"
            f"   Skipped : {skipped}\n"
            f"   Failed  : {failed}"
        ))
