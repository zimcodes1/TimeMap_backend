from rest_framework import serializers

from .models import DepartmentStudentCount


class DepartmentStudentCountSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source="department.name")
    department_code = serializers.ReadOnlyField(source="department.code")
    faculty_id = serializers.ReadOnlyField(source="department.faculty_id")
    faculty_name = serializers.ReadOnlyField(source="department.faculty.name")
    school_id = serializers.ReadOnlyField(source="department.faculty.school_id")
    school_name = serializers.ReadOnlyField(source="department.faculty.school.name")
    updated_by_name = serializers.ReadOnlyField(source="updated_by.full_name")

    class Meta:
        model = DepartmentStudentCount
        fields = (
            "id", "department", "department_name", "department_code",
            "faculty_id", "faculty_name", "school_id", "school_name",
            "level", "count", "updated_by", "updated_by_name", "updated_at",
        )
        read_only_fields = (
            "id", "updated_by", "updated_by_name", "updated_at",
            "department_name", "department_code", "faculty_id", "faculty_name",
            "school_id", "school_name",
        )

    def validate_department(self, department):
        profile = getattr(self.context["request"].user, "admin_profile", None)
        if profile and profile.level == "department" and department.id != profile.scope_department_id:
            raise serializers.ValidationError("You can only record the total for your assigned department.")
        return department

    def validate(self, attrs):
        profile = getattr(self.context["request"].user, "admin_profile", None)
        if self.instance and profile and self.instance.department_id != profile.scope_department_id:
            raise serializers.ValidationError("You can only update your assigned department total.")
        if self.instance and "level" in attrs and attrs["level"] != self.instance.level:
            raise serializers.ValidationError({"level": "Academic level cannot be changed; update the existing total or create a separate level record."})
        return attrs

    def validate_level(self, level):
        department = self.initial_data.get("department")
        if self.instance:
            max_level = self.instance.department.max_level
        elif department:
            from hierarchy.models import Department
            try:
                max_level = Department.objects.get(pk=department).max_level
            except Department.DoesNotExist:
                return level
        else:
            return level
        if level < 100 or level % 100 or level > max_level:
            raise serializers.ValidationError(f"Level must be between 100L and {max_level}L in 100-level increments.")
        return level


class StudentCountAnalyticsQuerySerializer(serializers.Serializer):
    department_id = serializers.IntegerField(required=False)
    faculty_id = serializers.IntegerField(required=False)
    school_id = serializers.IntegerField(required=False)
    level = serializers.IntegerField(required=False)
