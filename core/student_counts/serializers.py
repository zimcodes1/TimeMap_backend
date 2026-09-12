from rest_framework import serializers

from .models import ProgramStudentCount


class ProgramStudentCountSerializer(serializers.ModelSerializer):
    program_name = serializers.ReadOnlyField(source="program.name")
    program_code = serializers.ReadOnlyField(source="program.code")
    department_id = serializers.ReadOnlyField(source="program.department_id")
    department_name = serializers.ReadOnlyField(source="program.department.name")
    department_code = serializers.ReadOnlyField(source="program.department.code")
    faculty_id = serializers.ReadOnlyField(source="program.department.faculty_id")
    faculty_name = serializers.ReadOnlyField(source="program.department.faculty.name")
    school_id = serializers.ReadOnlyField(source="program.department.faculty.school_id")
    school_name = serializers.ReadOnlyField(source="program.department.faculty.school.name")
    updated_by_name = serializers.ReadOnlyField(source="updated_by.full_name")

    class Meta:
        model = ProgramStudentCount
        fields = (
            "id", "program", "program_name", "program_code",
            "department_id", "department_name", "department_code",
            "faculty_id", "faculty_name", "school_id", "school_name",
            "level", "count", "updated_by", "updated_by_name", "updated_at",
        )
        read_only_fields = (
            "id", "updated_by", "updated_by_name", "updated_at",
            "program_name", "program_code",
            "department_id", "department_name", "department_code",
            "faculty_id", "faculty_name", "school_id", "school_name",
        )

    def validate_program(self, program):
        profile = getattr(self.context["request"].user, "admin_profile", None)
        if profile and profile.level == "department":
            if program.department_id != profile.scope_department_id:
                raise serializers.ValidationError("You can only record totals for programs in your assigned department.")
        return program

    def validate(self, attrs):
        profile = getattr(self.context["request"].user, "admin_profile", None)
        if self.instance and profile and self.instance.program.department_id != profile.scope_department_id:
            raise serializers.ValidationError("You can only update totals for your assigned department's programs.")
        if self.instance and "level" in attrs and attrs["level"] != self.instance.level:
            raise serializers.ValidationError({"level": "Academic level cannot be changed; update the existing total or create a separate level record."})
        return attrs

    def validate_level(self, level):
        program_id = self.initial_data.get("program")
        if self.instance:
            max_level = self.instance.program.max_level
        elif program_id:
            from hierarchy.models import Program
            try:
                max_level = Program.objects.get(pk=program_id).max_level
            except Program.DoesNotExist:
                return level
        else:
            return level
        if level < 100 or level % 100 or level > max_level:
            raise serializers.ValidationError(f"Level must be between 100L and {max_level}L in 100-level increments.")
        return level


class StudentCountAnalyticsQuerySerializer(serializers.Serializer):
    program_id = serializers.IntegerField(required=False)
    department_id = serializers.IntegerField(required=False)
    faculty_id = serializers.IntegerField(required=False)
    school_id = serializers.IntegerField(required=False)
    level = serializers.IntegerField(required=False)
