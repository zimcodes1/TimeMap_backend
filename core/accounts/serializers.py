from django.contrib.auth import authenticate
from hierarchy.models import Department, Faculty, School
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AdminOfficer, LecturerStaff, Student, User

DEFAULT_NEW_USER_PASSWORD = "12345678"


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
