import re
from django.core.exceptions import ValidationError
from django.db import models


def validate_code_format(value):
    if not value or not isinstance(value, str):
        raise ValidationError("Code must be a non-empty string.")
    cleaned = value.strip().upper()
    if not re.match(r"^[A-Z0-9]+$", cleaned):
        raise ValidationError("Code must be alphanumeric without spaces or special characters.")


class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=20, unique=True, validators=[validate_code_format])
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Faculty(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="faculties")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True, validators=[validate_code_format])
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True, validators=[validate_code_format])
    max_level = models.PositiveIntegerField(default=400)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        if self.max_level and self.max_level < 100:
            raise ValidationError("Max level must be at least 100.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def computed_max_level(self):
        """Max level across all programs in this department."""
        from_programs = self.programs.aggregate(models.Max("max_level"))["max_level__max"]
        return from_programs if from_programs else self.max_level

    def __str__(self):
        return f"{self.name} ({self.code})"


class Program(models.Model):
    """
    An academic program within a department.
    E.g., Computer Science dept may have: Cyber Security, Data Science, Software Engineering, General CS.
    A default program (matching the department name) is auto-created when a department is created.
    """

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="programs")
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, validators=[validate_code_format])
    max_level = models.PositiveIntegerField(default=400)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("department", "code"), name="unique_program_code_per_department"),
            models.UniqueConstraint(
                fields=("department",),
                condition=models.Q(is_default=True),
                name="unique_default_program_per_department",
            ),
        ]
        ordering = ["department__name", "name"]

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
        if self.max_level and self.max_level < 100:
            raise ValidationError("Max level must be at least 100.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_default:
            raise ValidationError("The default program cannot be deleted.")
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code}) - {self.department.code}"
