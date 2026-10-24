"""
AttendanceChimp models.
 
Setup notes:
- This file defines a custom User model, so set AUTH_USER_MODEL = "<app_label>.User"
  in settings.py BEFORE running the first migration.
- QRUpload.image is an ImageField, which requires Pillow (pip install Pillow).
- Model.clean() is not called by save(). ModelForms/admin call it automatically;
  if you create QRUpload objects in a view or serializer, call full_clean() first.

Prompt used:
Please generate a suitable models.py in django based on the following specifications below.  Make sure the code is suitable for the specifications and do not add addtional features unrelated to the specifications.
AttendanceChimp Summary
AttendanceChimp tracks class attendance via QR codes:
• Users: students and instructors (two roles).
• Courses: each has one instructor. Students can enroll in multiple courses.
• Lectures: individual class meetings, each associated with a course.
• QR Code Uploads: photos uploaded by students, each associated with a student and a
lecture.
Design requirements: simple to use, supports attendance analytics, robust to cheating
"""
import hashlib
import secrets
 
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
 
 
def generate_qr_token():
    """Unguessable per-lecture secret that is encoded in the lecture's QR code."""
    return secrets.token_urlsafe(32)
 
 
class User(AbstractUser):
    """A user is either a student or an instructor."""
 
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        INSTRUCTOR = "instructor", "Instructor"
 
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )
 
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
 
    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR
 
 
class Course(models.Model):
    """A course has exactly one instructor; students may enroll in many courses."""
 
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,  # don't lose attendance history if an instructor is deleted
        related_name="courses_taught",
        limit_choices_to={"role": User.Role.INSTRUCTOR},
    )
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="courses_enrolled",
        blank=True,
        limit_choices_to={"role": User.Role.STUDENT},
    )
 
    def clean(self):
        super().clean()
        if self.instructor_id and not self.instructor.is_instructor:
            raise ValidationError({"instructor": "The selected user is not an instructor."})
 
    def __str__(self):
        return f"{self.code} - {self.name}"
 
 
class Lecture(models.Model):
    """
    A single class meeting for a course.
 
    qr_token is the secret encoded in this lecture's QR code. start_time/end_time
    define the window in which students may upload a photo of the code.
    """
 
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lectures",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    qr_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_qr_token,
        editable=False,
    )
 
    class Meta:
        ordering = ["-start_time"]
        indexes = [models.Index(fields=["course", "start_time"])]
 
    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})
 
    def __str__(self):
        return f"{self.course.code} - {self.start_time:%Y-%m-%d %H:%M}"
 
 
class QRUpload(models.Model):
    """
    A photo of a lecture's QR code uploaded by a student.
 
    An upload counts as that student's attendance for the lecture. Anti-cheating:
    - one upload per student per lecture
    - uploaded_at is set by the server, never by the client
    - uploads are only accepted during the lecture window, from enrolled students
    - image_hash (SHA-256) prevents the same file being submitted by multiple students
    """
 
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="qr_uploads",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    lecture = models.ForeignKey(
        Lecture,
        on_delete=models.CASCADE,
        related_name="qr_uploads",
    )
    image = models.ImageField(upload_to="qr_uploads/%Y/%m/%d/")
    image_hash = models.CharField(max_length=64, editable=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "lecture"],
                name="unique_upload_per_student_per_lecture",
            ),
            models.UniqueConstraint(
                fields=["lecture", "image_hash"],
                name="unique_image_per_lecture",
            ),
        ]
        indexes = [models.Index(fields=["lecture", "uploaded_at"])]
 
    def clean(self):
        super().clean()
        if not (self.student_id and self.lecture_id):
            return
 
        if not self.student.is_student:
            raise ValidationError({"student": "Only students can upload QR codes."})
 
        if not self.lecture.course.students.filter(pk=self.student_id).exists():
            raise ValidationError("Student is not enrolled in this lecture's course.")
 
        # Only enforce the time window when the upload is first created.
        if self._state.adding:
            now = timezone.now()
            if not (self.lecture.start_time <= now <= self.lecture.end_time):
                raise ValidationError("Uploads are only accepted during the lecture.")
 
    def save(self, *args, **kwargs):
        if self.image and not self.image_hash:
            hasher = hashlib.sha256()
            for chunk in self.image.chunks():
                hasher.update(chunk)
            self.image.seek(0)
            self.image_hash = hasher.hexdigest()
        super().save(*args, **kwargs)
 
    def __str__(self):
        return f"{self.student} @ {self.lecture}"