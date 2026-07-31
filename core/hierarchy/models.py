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
