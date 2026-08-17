from rest_framework import serializers
from .models import Department, Faculty, School


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


class DepartmentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.ReadOnlyField(source="faculty.name")
    school_name = serializers.ReadOnlyField(source="faculty.school.name")

    class Meta:
        model = Department
        fields = ("id", "faculty", "faculty_name", "school_name", "name", "code", "max_level", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_code(self, value):
        return value.strip().upper()
