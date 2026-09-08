from accounts.models import AdminOfficer
from django.core.validators import MinValueValidator
from django.db import models
from hierarchy.models import Department


class DepartmentStudentCount(models.Model):
    """The current planning population for a department, independent of user accounts."""

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="student_counts",
    )
    level = models.PositiveIntegerField()
    count = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    updated_by = models.ForeignKey(
        AdminOfficer,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_student_counts",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("department__faculty__school__name", "department__faculty__name", "department__name", "level")
        constraints = [
            models.UniqueConstraint(fields=("department", "level"), name="unique_department_student_count_level"),
        ]

    def __str__(self):
        return f"{self.department.code} {self.level}L: {self.count} students"
