from accounts.models import AdminOfficer
from django.core.validators import MinValueValidator
from django.db import models
from hierarchy.models import Program


class ProgramStudentCount(models.Model):
    """The current planning population for a program, independent of user accounts."""

    program = models.ForeignKey(
        Program,
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
        ordering = (
            "program__department__faculty__school__name",
            "program__department__faculty__name",
            "program__department__name",
            "program__name",
            "level",
        )
        constraints = [
            models.UniqueConstraint(fields=("program", "level"), name="unique_program_student_count_level"),
        ]

    def __str__(self):
        return f"{self.program.code} {self.level}L: {self.count} students"
