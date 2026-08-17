from django.contrib.auth import authenticate
from hierarchy.models import Department, Faculty, School
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AdminOfficer, LecturerStaff, Student, User

from .permissions import get_user_scope_departments

DEFAULT_NEW_USER_PASSWORD = "12345678"


def check_email_uniqueness(email, current_user_id=None):
    if not email:
        return
    email_clean = email.strip().lower()

    # Check Student
    qs_student = Student.objects.filter(email__iexact=email_clean)
    if current_user_id:
        qs_student = qs_student.exclude(user_id=current_user_id)
    if qs_student.exists():
        raise serializers.ValidationError({"email": f"A user with email '{email_clean}' already exists."})

    # Check LecturerStaff
    qs_lecturer = LecturerStaff.objects.filter(email__iexact=email_clean)
    if current_user_id:
        qs_lecturer = qs_lecturer.exclude(user_id=current_user_id)
    if qs_lecturer.exists():
        raise serializers.ValidationError({"email": f"A user with email '{email_clean}' already exists."})

    # Check AdminOfficer
    qs_admin = AdminOfficer.objects.filter(email__iexact=email_clean)
    if current_user_id:
        qs_admin = qs_admin.exclude(user_id=current_user_id)
    if qs_admin.exists():
        raise serializers.ValidationError({"email": f"A user with email '{email_clean}' already exists."})


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "identifier", "role", "requires_password_reset", "is_active", "last_login_at", "created_at")
        read_only_fields = ("id", "last_login_at", "created_at")


class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Student
        fields = ("id", "user", "matric_number", "full_name", "department", "level", "is_class_rep", "email")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.department:
            data["department_id"] = instance.department.id
            data["department"] = instance.department.name
        return data

    def validate(self, attrs):
        instance = self.instance
        current_user_id = instance.user_id if instance else None
        request = self.context.get("request")

        # 1. Email Uniqueness
        email = attrs.get("email") if "email" in attrs else (instance.email if instance else None)
        if email:
            check_email_uniqueness(email, current_user_id=current_user_id)

        # 2. Matric Number Uniqueness
        matric_number = attrs.get("matric_number") if "matric_number" in attrs else (instance.matric_number if instance else None)
        if matric_number:
            matric_clean = matric_number.strip().upper()
            qs_user = User.objects.filter(identifier=matric_clean)
            if current_user_id:
                qs_user = qs_user.exclude(id=current_user_id)
            if qs_user.exists():
                raise serializers.ValidationError({"matric_number": f"Matric number or identifier '{matric_clean}' is already registered."})

        # 3. Department Level & Scoped Permission Check
        department = attrs.get("department") if "department" in attrs else (instance.department if instance else None)
        level = attrs.get("level") if "level" in attrs else (instance.level if instance else None)

        if request and request.user and request.user.is_authenticated and department:
            allowed_depts = get_user_scope_departments(request.user)
            if not allowed_depts.filter(id=department.id).exists():
                raise serializers.ValidationError({"department": "You do not have permission to assign students to this department."})

        if department and level is not None:
            max_lvl = getattr(department, "max_level", 400)
            if level < 100 or level > max_lvl:
                raise serializers.ValidationError({
                    "level": f"Level {level}L is outside the allowed level range (100L - {max_lvl}L) for {department.name}."
                })

        # 4. Class Rep Restriction (Max 2 per Department & Level)
        is_class_rep = attrs.get("is_class_rep") if "is_class_rep" in attrs else (instance.is_class_rep if instance else False)
        if is_class_rep and department and level is not None:
            reps_qs = Student.objects.filter(department=department, level=level, is_class_rep=True)
            if instance:
                reps_qs = reps_qs.exclude(id=instance.id)
            if reps_qs.count() >= 2:
                raise serializers.ValidationError({
                    "is_class_rep": f"Department {department.code} already has the maximum limit of 2 class reps for level {level}L."
                })

        return attrs

    def create(self, validated_data):
        matric_number = validated_data.get("matric_number", "").strip().upper()
        user, created = User.objects.get_or_create(
            identifier=matric_number,
            defaults={
                "role": User.Role.STUDENT,
                "requires_password_reset": True,
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEFAULT_NEW_USER_PASSWORD)
            user.save()

        student = Student.objects.create(user=user, **validated_data)
        return student

    def update(self, instance, validated_data):
        matric_number = validated_data.get("matric_number")
        if matric_number and instance.user.identifier != matric_number.strip().upper():
            instance.user.identifier = matric_number.strip().upper()
            instance.user.save()
        return super().update(instance, validated_data)


class LecturerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = LecturerStaff
        fields = ("id", "user", "staff_id", "full_name", "department", "email")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.department:
            data["department_id"] = instance.department.id
            data["department"] = instance.department.name
        return data

    def validate(self, attrs):
        instance = self.instance
        current_user_id = instance.user_id if instance else None
        request = self.context.get("request")

        email = attrs.get("email") if "email" in attrs else (instance.email if instance else None)
        if email:
            check_email_uniqueness(email, current_user_id=current_user_id)

        staff_id = attrs.get("staff_id") if "staff_id" in attrs else (instance.staff_id if instance else None)
        if staff_id:
            staff_clean = staff_id.strip().upper()
            qs_user = User.objects.filter(identifier=staff_clean)
            if current_user_id:
                qs_user = qs_user.exclude(id=current_user_id)
            if qs_user.exists():
                raise serializers.ValidationError({"staff_id": f"Staff ID or identifier '{staff_clean}' is already registered."})

        department = attrs.get("department") if "department" in attrs else (instance.department if instance else None)
        if request and request.user and request.user.is_authenticated and department:
            allowed_depts = get_user_scope_departments(request.user)
            if not allowed_depts.filter(id=department.id).exists():
                raise serializers.ValidationError({"department": "You do not have permission to assign lecturers to this department."})

        return attrs

    def create(self, validated_data):
        staff_id = validated_data.get("staff_id", "").strip().upper()
        user, created = User.objects.get_or_create(
            identifier=staff_id,
            defaults={
                "role": User.Role.LECTURER,
                "requires_password_reset": True,
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEFAULT_NEW_USER_PASSWORD)
            user.save()

        lecturer = LecturerStaff.objects.create(user=user, **validated_data)
        return lecturer

    def update(self, instance, validated_data):
        staff_id = validated_data.get("staff_id")
        if staff_id and instance.user.identifier != staff_id.strip().upper():
            instance.user.identifier = staff_id.strip().upper()
            instance.user.save()
        return super().update(instance, validated_data)


class AdminProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = AdminOfficer
        fields = (
            "id",
            "user",
            "staff_id",
            "full_name",
            "level",
            "email",
            "scope_department",
            "scope_faculty",
            "scope_school",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        scope_id = None
        scope_name = None
        if instance.level == "department" and instance.scope_department:
            scope_id = instance.scope_department.id
            scope_name = instance.scope_department.name
            data["scope_department_id"] = instance.scope_department.id
            data["scope_department"] = instance.scope_department.name
            data["department"] = instance.scope_department.name
        elif instance.level == "faculty" and instance.scope_faculty:
            scope_id = instance.scope_faculty.id
            scope_name = instance.scope_faculty.name
            data["scope_faculty_id"] = instance.scope_faculty.id
            data["scope_faculty"] = instance.scope_faculty.name
        elif instance.level == "school" and instance.scope_school:
            scope_id = instance.scope_school.id
            scope_name = instance.scope_school.name
            data["scope_school_id"] = instance.scope_school.id
            data["scope_school"] = instance.scope_school.name

        data["scope_level"] = instance.level
        data["scope_id"] = scope_id
        data["scope_name"] = scope_name
        return data

    def validate(self, attrs):
        instance = self.instance
        current_user_id = instance.user_id if instance else None
        request = self.context.get("request")

        email = attrs.get("email") if "email" in attrs else (instance.email if instance else None)
        if email:
            check_email_uniqueness(email, current_user_id=current_user_id)

        staff_id = attrs.get("staff_id") if "staff_id" in attrs else (instance.staff_id if instance else None)
        if staff_id:
            staff_clean = staff_id.strip().upper()
            qs_user = User.objects.filter(identifier=staff_clean)
            if current_user_id:
                qs_user = qs_user.exclude(id=current_user_id)
            if qs_user.exists():
                raise serializers.ValidationError({"staff_id": f"Staff ID or identifier '{staff_clean}' is already registered."})

        # Enforce administrative level hierarchy & scope boundary rules
        if request and request.user and request.user.is_authenticated:
            req_user = request.user
            if not (req_user.is_superuser or (req_user.is_staff and not hasattr(req_user, "admin_profile"))):
                if hasattr(req_user, "admin_profile"):
                    admin_prof = req_user.admin_profile
                    target_level = attrs.get("level") if "level" in attrs else (instance.level if instance else None)
                    scope_dept = attrs.get("scope_department") if "scope_department" in attrs else (instance.scope_department if instance else None)
                    scope_fac = attrs.get("scope_faculty") if "scope_faculty" in attrs else (instance.scope_faculty if instance else None)

                    if admin_prof.level == "department":
                        raise serializers.ValidationError({"detail": "Department level admins cannot create or modify admin officer accounts."})

                    elif admin_prof.level == "faculty":
                        if target_level != "department":
                            raise serializers.ValidationError({"level": "Faculty level admins can only create or manage department level admin accounts."})
                        if scope_dept:
                            if not admin_prof.scope_faculty or scope_dept.faculty_id != admin_prof.scope_faculty.id:
                                raise serializers.ValidationError({"scope_department": "Selected department does not belong to your assigned faculty scope."})

                    elif admin_prof.level == "school":
                        if target_level == "school":
                            raise serializers.ValidationError({"level": "School level admins cannot create or manage school level admin accounts."})
                        if target_level == "faculty" and scope_fac:
                            if not admin_prof.scope_school or scope_fac.school_id != admin_prof.scope_school.id:
                                raise serializers.ValidationError({"scope_faculty": "Selected faculty does not belong to your assigned school scope."})
                        elif target_level == "department" and scope_dept:
                            if not admin_prof.scope_school or scope_dept.faculty.school_id != admin_prof.scope_school.id:
                                raise serializers.ValidationError({"scope_department": "Selected department does not belong to your assigned school scope."})

        return attrs


    def create(self, validated_data):
        staff_id = validated_data.get("staff_id", "").strip().upper()
        user, created = User.objects.get_or_create(
            identifier=staff_id,
            defaults={
                "role": User.Role.ADMIN,
                "requires_password_reset": True,
                "is_active": True,
            },
        )
        if created:
            user.set_password(DEFAULT_NEW_USER_PASSWORD)
            user.save()

        admin_officer = AdminOfficer.objects.create(user=user, **validated_data)
        return admin_officer

    def update(self, instance, validated_data):
        staff_id = validated_data.get("staff_id")
        if staff_id and instance.user.identifier != staff_id.strip().upper():
            instance.user.identifier = staff_id.strip().upper()
            instance.user.save()
        return super().update(instance, validated_data)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip().upper()
        password = attrs.get("password", "")

        try:
            user = User.objects.get(identifier=identifier)
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid identifier or password."})

        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid identifier or password."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "User account is disabled."})

        refresh = RefreshToken.for_user(user)

        # Retrieve profile payload
        profile_data = None
        if user.role == "student" and hasattr(user, "student_profile"):
            profile_data = StudentProfileSerializer(user.student_profile).data
        elif user.role == "lecturer" and hasattr(user, "lecturer_profile"):
            profile_data = LecturerProfileSerializer(user.lecturer_profile).data
        elif user.role == "admin" and hasattr(user, "admin_profile"):
            profile_data = AdminProfileSerializer(user.admin_profile).data

        attrs["user"] = user
        attrs["tokens"] = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        attrs["requires_password_reset"] = user.requires_password_reset
        attrs["profile"] = profile_data
        return attrs


class PasswordResetSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True, min_length=6, write_only=True)

    def validate_new_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters long.")
        return value
