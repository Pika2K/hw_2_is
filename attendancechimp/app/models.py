"""
models.py — Data model for AttendanceChimp.

AttendanceChimp is an electronic class attendance tool.  Instructors create
courses and lectures; each lecture is assigned a random QR code.  Students
photograph the QR code and upload the image.  The system decodes the QR code,
matches it to a lecture, and records the attendance.

Entities
--------
- CourseProfile   : extends Django User → instructor-specific data
- StudentProfile  : extends Django User → student-specific data
- Course          : a course taught by one instructor
- Enrollment      : junction table linking students to courses
- Lecture         : a single class meeting (has a QR-code identifier)
- QRCodeUpload    : a student's uploaded QR-code photograph
"""

from django.db import models
from django.contrib.auth.models import User

import logging
import string
import random
import uuid

logger = logging.getLogger(__name__) # set up tracking, auditing, and debugging
                                                               # allows using logger.warning(), logger.error(), 
                                                               # logger.info(), etc. Better than print() for debuggin... 


# ---------------------------------------------------------------------------
# User profiles
# ---------------------------------------------------------------------------

class InstructorProfile(models.Model):
    """An teaching instructor, each linked to one profile and can teach multiple courses."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100, blank=True)
 
 
class StudentProfile(models.Model):
    """A student, each linked to one profile and can enroll in multiple courses."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=20, unique=True)


# ---------------------------------------------------------------------------
# Course
# ---------------------------------------------------------------------------

class Course(models.Model):
    """A course with one instructor and a weekly meeting schedule."""
    name = models.CharField(max_length=200)
    instructor = models.ForeignKey(InstructorProfile, on_delete=models.PROTECT)
    meeting_days = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

class Enrollment(models.Model):
    """Links one student to one course using a many-to-many relationship. Each student can enroll in multiple courses, and each course can have multiple students."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
 
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "course"], name="unique_enrollment")
        ]


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

class Lecture(models.Model):
    """A lecture session for a course with a unique QR code identifier. Each lecture is linked to one course and has a date/time."""
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date = models.DateTimeField()
    qr_identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

# ---------------------------------------------------------------------------
# QR Code Upload
# ---------------------------------------------------------------------------

class QRCodeUpload(models.Model):
    """A photo of a QR code uploaded by a student; the lecture may be empty."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE)
    lecture = models.ForeignKey(Lecture, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.FileField(upload_to="qr_uploads/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

# ---------------------------------------------------------------------------
# Helper / API functions
# ---------------------------------------------------------------------------



