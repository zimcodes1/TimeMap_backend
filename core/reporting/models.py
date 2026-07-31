from accounts.models import AdminOfficer, Student
from django.db import models
from scheduling.models import LectureSession


class ClassRepReport(models.Model):
    lecture_session = models.OneToOneField(LectureSession, on_delete=models.CASCADE, related_name="report")
    reported_by = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="reports")
    held = models.BooleanField()
    reason = models.TextField()
    reported_at = models.DateTimeField(auto_now_add=True)
    window_expires_at = models.DateTimeField()
    lecturer_response = models.TextField(null=True, blank=True)
    lecturer_responded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Report for session {self.lecture_session_id} (held={self.held})"


class UnreportedSessionFlag(models.Model):
    lecture_session = models.OneToOneField(LectureSession, on_delete=models.CASCADE, related_name="unreported_flag")
    flagged_at = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.ForeignKey(
        AdminOfficer, null=True, blank=True, on_delete=models.SET_NULL, related_name="acknowledged_flags"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Unreported Flag for session {self.lecture_session_id}"
