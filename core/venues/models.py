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
        EXAM_HALL = "exam_hall", "Exam Hall"
        MULTIPURPOSE = "multipurpose", "Multipurpose"

    class OwningLevel(models.TextChoices):
        DEPARTMENT = "department", "Department"
        FACULTY = "faculty", "Faculty"
        SCHOOL = "school", "School"

    name = models.CharField(max_length=255, unique=True)
    venue_type = models.CharField(max_length=30, choices=VenueType.choices)
    capacity = models.IntegerField()
    exam_capacity = models.IntegerField(null=True, blank=True)
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
