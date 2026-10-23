from django.db import models
from hierarchy.models import Department, Faculty, School


class Facility(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Venue(models.Model):
    class VenueType(models.TextChoices):
        LECTURE_HALL = "lecture_hall", "Lecture Hall"
        LABORATORY = "laboratory", "Laboratory"
        AUDITORIUM = "auditorium", "Auditorium"
        CBT_CENTER = "cbt_center", "CBT Exam Center"
        MULTIPURPOSE = "multipurpose", "Multipurpose"
        EXAM_HALL = "exam_hall", "CBT Exam Center (Legacy)"

    class OwningLevel(models.TextChoices):
        DEPARTMENT = "department", "Department"
        FACULTY = "faculty", "Faculty"
        SCHOOL = "school", "School"

    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, blank=True, default="")
    venue_type = models.CharField(max_length=30, choices=VenueType.choices)
    capacity = models.IntegerField(default=0)
    exam_capacity = models.IntegerField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True, default="")
    facilities = models.ManyToManyField(Facility, blank=True, related_name="venues")

    owning_level = models.CharField(max_length=20, choices=OwningLevel.choices)
    owning_department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_venues"
    )
    owning_faculty = models.ForeignKey(
        Faculty, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_venues"
    )
    owning_school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_venues"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.capacity})"
