from accounts.models import AdminOfficer, Student
from hierarchy.models import Department, Faculty, School
from rest_framework import serializers

from .models import Course, CourseAccessGrant, CourseRegistration
from .services import get_visible_courses_for_student


class CourseSerializer(serializers.ModelSerializer):
    owning_department_name = serializers.ReadOnlyField(source="owning_department.name")
    owning_faculty_name = serializers.ReadOnlyField(source="owning_faculty.name")
    owning_school_name = serializers.ReadOnlyField(source="owning_school.name")
    registration_count = serializers.SerializerMethodField()

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
            "registration_count",
        )
        read_only_fields = ("id",)

    def get_registration_count(self, obj):
        return obj.student_registrations.count()

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs

        user = request.user
        owning_level = attrs.get("owning_level", self.instance.owning_level if self.instance else None)
        owning_dept = attrs.get("owning_department", self.instance.owning_department if self.instance else None)
        owning_fac = attrs.get("owning_faculty", self.instance.owning_faculty if self.instance else None)
        owning_sch = attrs.get("owning_school", self.instance.owning_school if self.instance else None)

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
            if admin_prof.level == "university":
                raise serializers.ValidationError("University level admins have view-only access and cannot create or edit courses.")

            elif admin_prof.level == "school":
                if owning_level != Course.OwningLevel.SCHOOL:
                    raise serializers.ValidationError({"owning_level": "School level admins can only create school-owned courses."})
                if admin_prof.scope_school and owning_sch != admin_prof.scope_school:
                    raise serializers.ValidationError({"owning_school": "School level admins can only create courses for their assigned school scope."})

            elif admin_prof.level == "faculty":
                if owning_level != Course.OwningLevel.FACULTY:
                    raise serializers.ValidationError({"owning_level": "Faculty level admins can only create faculty-owned courses."})
                if admin_prof.scope_faculty and owning_fac != admin_prof.scope_faculty:
                    raise serializers.ValidationError({"owning_faculty": "Faculty level admins can only create courses for their assigned faculty scope."})

            elif admin_prof.level == "department":
                if owning_level != Course.OwningLevel.DEPARTMENT:
                    raise serializers.ValidationError({"owning_level": "Department admins can only create department-owned courses."})
                if admin_prof.scope_department and owning_dept != admin_prof.scope_department:
                    raise serializers.ValidationError({"owning_department": "Department admins can only create courses for their assigned department scope."})

        return attrs


class CourseAccessGrantSerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="course.code")
    course_title = serializers.ReadOnlyField(source="course.title")
    granted_to_department_name = serializers.ReadOnlyField(source="granted_to_department.name")
    granted_to_faculty_name = serializers.ReadOnlyField(source="granted_to_faculty.name")
    granted_to_school_name = serializers.ReadOnlyField(source="granted_to_school.name")
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
            "granted_to_department_name",
            "granted_to_faculty",
            "granted_to_faculty_name",
            "granted_to_school",
            "granted_to_school_name",
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
