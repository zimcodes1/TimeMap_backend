from accounts.models import AdminOfficer, Student
from hierarchy.models import Department, Faculty, School
from rest_framework import serializers

from .models import Course, CourseAccessGrant, CourseRegistration
from .services import get_visible_courses_for_student


class CourseSerializer(serializers.ModelSerializer):
    owning_department_name = serializers.ReadOnlyField(source="owning_department.name")
    owning_faculty_name = serializers.ReadOnlyField(source="owning_faculty.name")
    owning_school_name = serializers.ReadOnlyField(source="owning_school.name")

    class Meta:
        model = Course
        fields = (
            "id",
            "code",
            "title",
            "level",
            "owning_level",
            "owning_department",
            "owning_department_name",
            "owning_faculty",
            "owning_faculty_name",
            "owning_school",
            "owning_school_name",
            "lecturers",
        )
        read_only_fields = ("id",)

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs

        user = request.user
        owning_level = attrs.get("owning_level")
        owning_dept = attrs.get("owning_department")
        owning_fac = attrs.get("owning_faculty")
        owning_sch = attrs.get("owning_school")

        # Validate that only matching ownership field is set
        if owning_level == Course.OwningLevel.DEPARTMENT and not owning_dept:
            raise serializers.ValidationError({"owning_department": "owning_department is required for department-owned course."})
        if owning_level == Course.OwningLevel.FACULTY and not owning_fac:
            raise serializers.ValidationError({"owning_faculty": "owning_faculty is required for faculty-owned course."})
        if owning_level == Course.OwningLevel.SCHOOL and not owning_sch:
            raise serializers.ValidationError({"owning_school": "owning_school is required for school-owned course."})

        # Creation-time ownership guardrails based on requesting admin's level
        if user.role == "admin" and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            if admin_prof.level == "department":
                if owning_level != Course.OwningLevel.DEPARTMENT or owning_dept != admin_prof.scope_department:
                    raise serializers.ValidationError("Department admins can only create department-owned courses for their own department.")
            elif admin_prof.level == "faculty":
                if owning_level in [Course.OwningLevel.SCHOOL, Course.OwningLevel.GENERAL]:
                    raise serializers.ValidationError("Faculty admins cannot create school-level or general courses.")
                if owning_level == Course.OwningLevel.FACULTY and owning_fac != admin_prof.scope_faculty:
                    raise serializers.ValidationError("Faculty admins can only create faculty-owned courses for their own faculty.")

        return attrs


class CourseAccessGrantSerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="course.code")
    course_title = serializers.ReadOnlyField(source="course.title")
    initiated_by_name = serializers.ReadOnlyField(source="initiated_by.full_name")
    decided_by_name = serializers.ReadOnlyField(source="decided_by.full_name")

    class Meta:
        model = CourseAccessGrant
        fields = (
            "id",
            "course",
            "course_code",
            "course_title",
            "granted_to_level",
            "granted_to_department",
            "granted_to_faculty",
            "granted_to_school",
            "direction",
            "status",
            "initiated_by",
            "initiated_by_name",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "created_at",
        )
        read_only_fields = ("id", "initiated_by", "decided_by", "decided_at", "created_at")


class CourseRegistrationSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all(), required=False, default=None)
    course_code = serializers.ReadOnlyField(source="course.code")
    course_title = serializers.ReadOnlyField(source="course.title")
    student_name = serializers.ReadOnlyField(source="student.full_name")
    matric_number = serializers.ReadOnlyField(source="student.matric_number")

    class Meta:
        model = CourseRegistration
        fields = (
            "id",
            "student",
            "student_name",
            "matric_number",
            "course",
            "course_code",
            "course_title",
            "academic_session",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user and request.user.role == "student" and hasattr(request.user, "student_profile"):
            if not attrs.get("student"):
                attrs["student"] = request.user.student_profile

        student = attrs.get("student")
        course = attrs.get("course")

        if not student:
            raise serializers.ValidationError({"student": "Student profile is required for registration."})

        if student and course:
            visible_courses = get_visible_courses_for_student(student)
            if not visible_courses.filter(id=course.id).exists():
                raise serializers.ValidationError({"course": "This course is not visible or accessible to your department/faculty."})

        return attrs
