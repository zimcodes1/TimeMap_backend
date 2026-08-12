from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from hierarchy.models import Department, Faculty, School


class UserManager(BaseUserManager):
    def create_user(self, identifier, password=None, role="student", **extra_fields):
        if not identifier:
            raise ValueError("The Identifier field must be set")
        identifier = identifier.strip().upper()
        user = self.model(identifier=identifier, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, identifier, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("requires_password_reset", False)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(identifier, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"
        ADMIN = "admin", "Admin"

    identifier = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    requires_password_reset = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "identifier"
    REQUIRED_FIELDS = []

    def clean(self):
        super().clean()
        if self.identifier:
            self.identifier = self.identifier.strip().upper()

    def save(self, *args, **kwargs):
        if self.identifier:
            self.identifier = self.identifier.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.identifier} ({self.role})"


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    matric_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="students")
    level = models.IntegerField()
    is_class_rep = models.BooleanField(default=False)
    email = models.EmailField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.matric_number:
            self.matric_number = self.matric_number.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.matric_number})"


class LecturerStaff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="lecturer_profile")
    staff_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="lecturers")
    email = models.EmailField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.staff_id:
            self.staff_id = self.staff_id.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.staff_id})"


class AdminOfficer(models.Model):
    class Level(models.TextChoices):
        DEPARTMENT = "department", "Department"
        FACULTY = "faculty", "Faculty"
        SCHOOL = "school", "School"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    staff_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    level = models.CharField(max_length=20, choices=Level.choices)
    email = models.EmailField(null=True, blank=True)
    scope_department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="admin_officers"
    )
    scope_faculty = models.ForeignKey(
        Faculty, null=True, blank=True, on_delete=models.SET_NULL, related_name="admin_officers"
    )
    scope_school = models.ForeignKey(
        School, null=True, blank=True, on_delete=models.SET_NULL, related_name="admin_officers"
    )

    def save(self, *args, **kwargs):
        if self.staff_id:
            self.staff_id = self.staff_id.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.staff_id} - {self.level})"
