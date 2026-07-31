from accounts.models import AdminOfficer, LecturerStaff, Student
from django.db import models
from hierarchy.models import Department, Faculty, School


class Course(models.Model):
    class OwningLevel(models.TextChoices):
        DEPARTMENT = "department", "Department"
        FACULTY = "faculty", "Faculty"
        SCHOOL = "school", "School"
        GENERAL = "general", "General"

    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=255)
    level = models.IntegerField()

    owning_level = models.CharField(max_length=20, choices=OwningLevel.choices)
    owning_department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_courses"
    )
    owning_faculty = models.ForeignKey(
        Faculty, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_courses"
    )
    owning_school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_courses"
    )

    lecturers = models.ManyToManyField(LecturerStaff, blank=True, related_name="assigned_courses")

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.title}"


class CourseAccessGrant(models.Model):
    class GrantedToLevel(models.TextChoices):
        DEPARTMENT = "department", "Department"
        FACULTY = "faculty", "Faculty"
        SCHOOL = "school", "School"

    class Direction(models.TextChoices):
        OFFERED = "offered", "Offered"
        REQUESTED = "requested", "Requested"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="access_grants")
    granted_to_level = models.CharField(max_length=20, choices=GrantedToLevel.choices)
    granted_to_department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="course_access_grants"
    )
    granted_to_faculty = models.ForeignKey(
        Faculty, null=True, blank=True, on_delete=models.SET_NULL, related_name="course_access_grants"
    )
    granted_to_school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="course_access_grants"
    )

    direction = models.CharField(max_length=20, choices=Direction.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    initiated_by = models.ForeignKey(AdminOfficer, on_delete=models.CASCADE, related_name="initiated_course_grants")
    decided_by = models.ForeignKey(
        AdminOfficer, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_course_grants"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AccessGrant for {self.course.code} ({self.status})"


class CourseRegistration(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="course_registrations")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="student_registrations")
    academic_session = models.CharField(max_length=20)

    class Meta:
        unique_together = ("student", "course", "academic_session")

    def __str__(self):
        return f"{self.student.matric_number} registered for {self.course.code} ({self.academic_session})"
