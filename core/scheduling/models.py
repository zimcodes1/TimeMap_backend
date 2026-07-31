from accounts.models import AdminOfficer, LecturerStaff
from courses.models import Course
from django.db import models
from venues.models import Venue


class TimetableEntry(models.Model):
    class EntryType(models.TextChoices):
        LECTURE = "lecture", "Lecture"
        EXAM = "exam", "Exam"
        EVENT = "event", "Event"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        SHIFTED = "shifted", "Shifted"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"

    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_entries")
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="timetable_entries")
    start_time = models.TimeField()
    end_time = models.TimeField()

    recurrence_rule = models.CharField(max_length=255, null=True, blank=True)
    recurrence_start_date = models.DateField(null=True, blank=True)
    recurrence_end_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    created_by = models.ForeignKey(AdminOfficer, on_delete=models.CASCADE, related_name="created_timetable_entries")
    academic_session = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.entry_type} - {self.academic_session})"


class LectureSession(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        SHIFTED = "shifted", "Shifted"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"
        HELD = "held", "Held"
        NOT_HELD = "not_held", "Not Held"

    timetable_entry = models.ForeignKey(TimetableEntry, on_delete=models.CASCADE, related_name="sessions")
    session_date = models.DateField()
    session_start_time = models.TimeField()
    session_end_time = models.TimeField()
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="lecture_sessions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)

    def __str__(self):
        return f"Session for {self.timetable_entry.title} on {self.session_date}"


class ExamSitting(models.Model):
    timetable_entry = models.OneToOneField(TimetableEntry, on_delete=models.CASCADE, related_name="exam_sitting")
    registered_candidates_count = models.IntegerField()
    invigilators = models.ManyToManyField(LecturerStaff, blank=True, related_name="invigilated_exams")

    def __str__(self):
        return f"ExamSitting for {self.timetable_entry.title} ({self.registered_candidates_count} candidates)"
