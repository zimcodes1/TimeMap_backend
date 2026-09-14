import uuid
from accounts.models import AdminOfficer, LecturerStaff, User
from courses.models import Course
from django.core.exceptions import ValidationError
from django.db import models
from hierarchy.models import School
from venues.models import Venue


class AcademicSession(models.Model):
    """
    An academic session/year scoped to a specific school.
    Manually created by school-level admins.
    E.g., '2026/2027' for a particular school.
    """

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="academic_sessions")
    label = models.CharField(max_length=20)  # e.g., "2026/2027"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=("school", "label"), name="unique_session_label_per_school"),
            models.UniqueConstraint(
                fields=("school",),
                condition=models.Q(is_current=True),
                name="unique_current_session_per_school",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Session start date must be before end date.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} - {self.school.code}"


class Semester(models.Model):
    """
    A semester within an academic session, scoped to the session's school.
    Created by school-level admins with configurable duration and period types.
    """

    class SemesterName(models.TextChoices):
        FIRST = "first", "First Semester"
        SECOND = "second", "Second Semester"

    class DurationType(models.TextChoices):
        WEEKS = "weeks", "Weeks"
        MONTHS = "months", "Months"
        FIXED = "fixed", "Fixed End Date"

    session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name="semesters")
    name = models.CharField(max_length=20, choices=SemesterName.choices)
    start_date = models.DateField()
    end_date = models.DateField()

    # Duration specification (how the admin defined the length)
    duration_type = models.CharField(max_length=10, choices=DurationType.choices, default=DurationType.FIXED)
    duration_value = models.PositiveIntegerField(null=True, blank=True, help_text="Number of weeks or months if applicable.")

    # Period definitions
    lecture_start_date = models.DateField(null=True, blank=True)
    lecture_end_date = models.DateField(null=True, blank=True)
    exam_start_date = models.DateField(null=True, blank=True)
    exam_end_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        AdminOfficer, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="created_semesters",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("session", "name")
        ordering = ["session", "name"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError("Semester start date must be before end date.")
        if self.lecture_start_date and self.lecture_end_date and self.lecture_start_date >= self.lecture_end_date:
            raise ValidationError("Lecture period start must be before end.")
        if self.exam_start_date and self.exam_end_date and self.exam_start_date >= self.exam_end_date:
            raise ValidationError("Exam period start must be before end.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_name_display()} - {self.session.label} ({self.session.school.code})"


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
    semester = models.ForeignKey(Semester, null=True, blank=True, on_delete=models.SET_NULL, related_name="timetable_entries")
    academic_session = models.CharField(max_length=20, blank=True, default="")  # Deprecated — kept for data migration
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


class GenerationScopePermission(models.Model):
    """
    Controls decentralized timetable generation rights within a School.
    System administrators (superusers) configure whether Faculty or Department
    admins are permitted to run scoped GA timetable generation.
    """

    school = models.OneToOneField(
        School, on_delete=models.CASCADE, related_name="generation_permission"
    )
    allow_faculty_generation = models.BooleanField(default=False)
    allow_department_generation = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GenerationPermission({self.school.code}: fac={self.allow_faculty_generation}, dept={self.allow_department_generation})"


class TimetableGenerationRun(models.Model):
    """
    Tracks an automated timetable generation run produced by the Genetic Algorithm.
    Stores complete evaluation statistics, conflict diagnostics, and generated assignments.
    """

    class ScopeType(models.TextChoices):
        SCHOOL = "school", "School"
        FACULTY = "faculty", "Faculty"
        DEPARTMENT = "department", "Department"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class ResultStatus(models.TextChoices):
        OPTIMAL = "optimal", "Optimal"
        FEASIBLE = "feasible", "Feasible"
        BEST_AVAILABLE = "best_available", "Best Available"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="generation_runs"
    )
    scope_type = models.CharField(max_length=20, choices=ScopeType.choices)
    scope_id = models.PositiveIntegerField()
    scope_name = models.CharField(max_length=255, blank=True, default="")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    result_status = models.CharField(
        max_length=20, choices=ResultStatus.choices, default=ResultStatus.BEST_AVAILABLE
    )

    # Detailed constraint counters
    hard_conflicts_count = models.PositiveIntegerField(default=0)
    student_conflicts_count = models.PositiveIntegerField(default=0)
    lecturer_conflicts_count = models.PositiveIntegerField(default=0)
    venue_conflicts_count = models.PositiveIntegerField(default=0)
    daily_limit_violations_count = models.PositiveIntegerField(default=0)
    occurrence_day_violations_count = models.PositiveIntegerField(default=0)
    capacity_penalty = models.PositiveIntegerField(default=0)
    fitness_score = models.FloatField(default=0.0)

    # Diagnostics & assignments payload
    conflict_report = models.JSONField(default=dict, blank=True)
    generation_metrics = models.JSONField(default=dict, blank=True)
    assignments_payload = models.JSONField(default=list, blank=True)

    is_published = models.BooleanField(default=False)
    initiated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="timetable_generation_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"GenerationRun #{self.id} [{self.scope_type}:{self.scope_name}] ({self.status} - {self.result_status})"

