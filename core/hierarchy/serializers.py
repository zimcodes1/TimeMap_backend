from rest_framework import serializers
from .models import Department, Faculty, Program, School


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ("id", "name", "code", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_code(self, value):
        return value.strip().upper()


class FacultySerializer(serializers.ModelSerializer):
    school_name = serializers.ReadOnlyField(source="school.name")

    class Meta:
        model = Faculty
        fields = ("id", "school", "school_name", "name", "code", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
                if hasattr(user, "admin_profile") and user.admin_profile.level == "school":
                    school = attrs.get("school") if "school" in attrs else (self.instance.school if self.instance else None)
                    if school and user.admin_profile.scope_school_id and school.id != user.admin_profile.scope_school_id:
                        raise serializers.ValidationError({"school": "School level admins can only create or edit faculties under their assigned school."})
        return attrs


class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source="department.name")
    department_code = serializers.ReadOnlyField(source="department.code")
    faculty_id = serializers.ReadOnlyField(source="department.faculty.id")
    faculty_name = serializers.ReadOnlyField(source="department.faculty.name")
    school_id = serializers.ReadOnlyField(source="department.faculty.school.id")
    school_name = serializers.ReadOnlyField(source="department.faculty.school.name")

    class Meta:
        model = Program
        fields = (
            "id",
            "department",
            "department_name",
            "department_code",
            "faculty_id",
            "faculty_name",
            "school_id",
            "school_name",
            "name",
            "code",
            "max_level",
            "is_default",
            "created_at",
        )
        read_only_fields = (
            "id",
            "department_name",
            "department_code",
            "faculty_id",
            "faculty_name",
            "school_id",
            "school_name",
            "is_default",
            "created_at",
        )

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
                if hasattr(user, "admin_profile") and user.admin_profile.level == "department":
                    dept = attrs.get("department") if "department" in attrs else (self.instance.department if self.instance else None)
                    if dept and user.admin_profile.scope_department_id and dept.id != user.admin_profile.scope_department_id:
                        raise serializers.ValidationError({"department": "Department level admins can only create or edit programs under their assigned department."})
        return attrs


class DepartmentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.ReadOnlyField(source="faculty.name")
    school_name = serializers.ReadOnlyField(source="faculty.school.name")
    programs = ProgramSerializer(many=True, read_only=True)

    class Meta:
        model = Department
        fields = ("id", "faculty", "faculty_name", "school_name", "name", "code", "max_level", "programs", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
                if hasattr(user, "admin_profile") and user.admin_profile.level == "faculty":
                    faculty = attrs.get("faculty") if "faculty" in attrs else (self.instance.faculty if self.instance else None)
                    if faculty and user.admin_profile.scope_faculty_id and faculty.id != user.admin_profile.scope_faculty_id:
                        raise serializers.ValidationError({"faculty": "Faculty level admins can only create or edit departments under their assigned faculty."})
        return attrs

