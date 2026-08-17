from accounts.models import LecturerStaff, User
from courses.models import Course
from django.db import models


class CourseLectureSummarySnapshot(models.Model):
    """
    Stores pre-calculated or aggregated lecture statistics rollups for courses & lecturers.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="analytics_snapshots")
    lecturer = models.ForeignKey(LecturerStaff, on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_snapshots")
    start_date = models.DateField()
    end_date = models.DateField()
    total_sessions_scheduled = models.IntegerField(default=0)
    total_sessions_held = models.IntegerField(default=0)
    total_sessions_not_held = models.IntegerField(default=0)
    total_sessions_cancelled = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Snapshot ({self.course.code}) {self.start_date} to {self.end_date}"


class AnalyticsQueryLog(models.Model):
    """
    Audit log of analytics requests executed by users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="analytics_query_logs")
    query_type = models.CharField(max_length=50)  # "class_rep", "lecturer", "admin"
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    target_course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)
    target_lecturer = models.ForeignKey(LecturerStaff, on_delete=models.SET_NULL, null=True, blank=True)
    queried_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-queried_at"]

    def __str__(self):
        return f"AnalyticsLog ({self.query_type}) by {self.user.identifier} at {self.queried_at}"
