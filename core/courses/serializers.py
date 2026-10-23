from accounts.models import AdminOfficer, Student
from hierarchy.models import Department, Faculty, School
from rest_framework import serializers

from .models import Course, CourseAccessGrant, CourseRegistration
from .services import calculate_course_student_count, get_visible_courses_for_student


class CourseSerializer(serializers.ModelSerializer):
    owning_department_name = serializers.ReadOnlyField(source="owning_department.name")
    owning_faculty_name = serializers.ReadOnlyField(source="owning_faculty.name")
    owning_school_name = serializers.ReadOnlyField(source="owning_school.name")
    semester_name = serializers.ReadOnlyField(source="semester.get_name_display")
    session_label = serializers.ReadOnlyField(source="semester.session.label")
    target_program_name = serializers.ReadOnlyField(source="target_program.name")
    target_program_code = serializers.ReadOnlyField(source="target_program.code")
    registration_count = serializers.SerializerMethodField()
    is_granted_to_scope = serializers.BooleanField(read_only=True, default=False)
    can_edit_exam_settings = serializers.BooleanField(read_only=True, default=False)
    applicable_program_ids = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = (
            "id",
            "code",
            "title",
            "level",
            "course_type",
            "required_occurrences_per_week",
            "exam_type",
            "exam_duration_minutes",
            "exam_duration_per_student_minutes",
            "owning_level",
            "owning_department",
            "owning_department_name",
            "owning_faculty",
            "owning_faculty_name",
            "owning_school",
            "owning_school_name",
            "semester",
            "semester_name",
            "session_label",
            "program_scope",
            "target_program",
            "target_program_name",
            "target_program_code",
            "lecturers",
            "registration_count",
            "is_granted_to_scope",
            "can_edit_exam_settings",
            "applicable_program_ids",
        )
        read_only_fields = ("id", "is_granted_to_scope", "can_edit_exam_settings", "applicable_program_ids")

    def get_applicable_program_ids(self, obj):
        try:
            from .services import get_course_attributed_programs
            return list(get_course_attributed_programs(obj))
        except Exception:
            return []

    def get_registration_count(self, obj):
        if hasattr(obj, "_cached_registration_count"):
            return obj._cached_registration_count
        return calculate_course_student_count(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.owning_department:
            dept = instance.owning_department
            if dept.faculty:
                if not data.get("owning_faculty"):
                    data["owning_faculty"] = dept.faculty.id
                if not data.get("owning_faculty_name"):
                    data["owning_faculty_name"] = dept.faculty.name
                if dept.faculty.school:
                    if not data.get("owning_school"):
                        data["owning_school"] = dept.faculty.school.id
                    if not data.get("owning_school_name"):
                        data["owning_school_name"] = dept.faculty.school.name
        elif instance.owning_faculty:
            fac = instance.owning_faculty
            if fac.school:
                if not data.get("owning_school"):
                    data["owning_school"] = fac.school.id
                if not data.get("owning_school_name"):
                    data["owning_school_name"] = fac.school.name

        data["lecturers_details"] = [
            {
                "id": lec.id,
                "staff_id": lec.staff_id,
                "name": lec.full_name,
                "email": lec.email or "",
                "department_id": lec.department_id,
                "department_name": lec.department.name if lec.department else "",
            }
            for lec in instance.lecturers.all()
        ]

        # Check if course is owned by the user's scope or granted to it
        is_granted_to_scope = False
        can_edit_exam_settings = False
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            user = request.user
            admin_prof = getattr(user, "admin_profile", None)
            if admin_prof:
                level = admin_prof.level
                is_eo = getattr(admin_prof, "is_exam_officer", False)
                is_owned = False

                if level == "department" and admin_prof.scope_department_id:
                    is_owned = (
                        instance.owning_level == Course.OwningLevel.DEPARTMENT
                        and instance.owning_department_id == admin_prof.scope_department_id
                    )
                elif level == "faculty" and admin_prof.scope_faculty_id:
                    is_owned = (
                        instance.owning_level == Course.OwningLevel.FACULTY
                        and instance.owning_faculty_id == admin_prof.scope_faculty_id
                    )
                elif level == "school" and admin_prof.scope_school_id:
                    is_owned = (
                        instance.owning_level == Course.OwningLevel.SCHOOL
                        and instance.owning_school_id == admin_prof.scope_school_id
                    )
                elif user.is_superuser:
                    is_owned = True

                # Check if course was explicitly granted to this scope via CourseAccessGrant
                if not is_owned:
                    granted_ids = getattr(request, "_cached_granted_course_ids", None)
                    if granted_ids is None:
                        from django.db.models import Q
                        grant_q = Q()
                        if level == "department" and admin_prof.scope_department_id:
                            grant_q = Q(granted_to_department_id=admin_prof.scope_department_id)
                        elif level == "faculty" and admin_prof.scope_faculty_id:
                            grant_q = Q(granted_to_faculty_id=admin_prof.scope_faculty_id)
                        elif level == "school" and admin_prof.scope_school_id:
                            grant_q = Q(granted_to_school_id=admin_prof.scope_school_id)
                        if grant_q:
                            granted_ids = set(
                                CourseAccessGrant.objects.filter(
                                    grant_q, status=CourseAccessGrant.Status.APPROVED
                                ).values_list("course_id", flat=True)
                            )
                        else:
                            granted_ids = set()
                        setattr(request, "_cached_granted_course_ids", granted_ids)
                    is_granted_to_scope = instance.id in granted_ids
                else:
                    is_granted_to_scope = False

                has_scope_eo = getattr(request, "_cached_has_scope_eo", None)
                if has_scope_eo is None:
                    if is_eo:
                        has_scope_eo = True
                    elif level == "department" and admin_prof.scope_department_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_department_id=admin_prof.scope_department_id
                        ).exists()
                    elif level == "faculty" and admin_prof.scope_faculty_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_faculty_id=admin_prof.scope_faculty_id
                        ).exists()
                    elif level == "school" and admin_prof.scope_school_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_school_id=admin_prof.scope_school_id
                        ).exists()
                    else:
                        has_scope_eo = False
                    setattr(request, "_cached_has_scope_eo", has_scope_eo)

                can_edit_exam_settings = is_owned and (is_eo or not has_scope_eo)

        data["is_granted_to_scope"] = is_granted_to_scope
        data["can_edit_exam_settings"] = can_edit_exam_settings
        return data

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            return attrs

        user = request.user

        # Exam officer validation: cannot create courses, can only edit exam fields on owned courses
        if (user.role in ["admin", "system_admin"] or user.is_superuser) and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            is_eo = getattr(admin_prof, "is_exam_officer", False)
            level = admin_prof.level

            is_owned = False
            if level == "department" and admin_prof.scope_department_id:
                is_owned = bool(
                    self.instance
                    and self.instance.owning_level == Course.OwningLevel.DEPARTMENT
                    and self.instance.owning_department_id == admin_prof.scope_department_id
                )
            elif level == "faculty" and admin_prof.scope_faculty_id:
                is_owned = bool(
                    self.instance
                    and self.instance.owning_level == Course.OwningLevel.FACULTY
                    and self.instance.owning_faculty_id == admin_prof.scope_faculty_id
                )
            elif level == "school" and admin_prof.scope_school_id:
                is_owned = bool(
                    self.instance
                    and self.instance.owning_level == Course.OwningLevel.SCHOOL
                    and self.instance.owning_school_id == admin_prof.scope_school_id
                )
            elif user.is_superuser:
                is_owned = True

            EXAM_FIELDS = {"exam_type", "exam_duration_minutes", "exam_duration_per_student_minutes"}
            changed_fields = set()
            if self.instance:
                for key, val in attrs.items():
                    if getattr(self.instance, key, None) != val:
                        changed_fields.add(key)
            else:
                changed_fields = set(attrs.keys())

            exam_fields_changed = bool(changed_fields & EXAM_FIELDS)

            if is_eo:
                if not self.instance:
                    raise serializers.ValidationError("Exam officers cannot create courses.")
                disallowed = changed_fields - EXAM_FIELDS
                if disallowed:
                    raise serializers.ValidationError(
                        f"Exam officers can only modify exam settings (exam_type, exam_duration_minutes, exam_duration_per_student_minutes). Cannot modify: {', '.join(sorted(disallowed))}."
                    )
                if not is_owned:
                    raise serializers.ValidationError(
                        "Exam officers can only configure courses that are within and from their scope."
                    )
            elif exam_fields_changed and self.instance:
                if not is_owned:
                    raise serializers.ValidationError(
                        "Courses can only be configured by their originating scope's exam officer or admin."
                    )
                # Check if an exam officer exists for this scope; if so, admin cannot configure exam settings
                has_scope_eo = getattr(request, "_cached_has_scope_eo", None)
                if has_scope_eo is None:
                    if level == "department" and admin_prof.scope_department_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_department_id=admin_prof.scope_department_id
                        ).exists()
                    elif level == "faculty" and admin_prof.scope_faculty_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_faculty_id=admin_prof.scope_faculty_id
                        ).exists()
                    elif level == "school" and admin_prof.scope_school_id:
                        has_scope_eo = AdminOfficer.objects.filter(
                            is_exam_officer=True, user__is_active=True, scope_school_id=admin_prof.scope_school_id
                        ).exists()
                    else:
                        has_scope_eo = False
                    setattr(request, "_cached_has_scope_eo", has_scope_eo)
                if has_scope_eo:
                    raise serializers.ValidationError(
                        "An exam officer is assigned to your scope. Exam settings can only be configured by the assigned exam officer."
                    )

            # CBT examinations should not have a sitting window duration since total duration is calculated via throughput metrics
            exam_type = attrs.get("exam_type", getattr(self.instance, "exam_type", Course.ExamType.WRITTEN) if self.instance else Course.ExamType.WRITTEN)
            if exam_type == Course.ExamType.CBT:
                attrs["exam_duration_minutes"] = None
                if "exam_duration_per_student_minutes" in attrs:
                    if not attrs["exam_duration_per_student_minutes"]:
                        attrs["exam_duration_per_student_minutes"] = 45
                elif self.instance and not self.instance.exam_duration_per_student_minutes:
                    attrs["exam_duration_per_student_minutes"] = 45
            elif exam_type in [Course.ExamType.WRITTEN, Course.ExamType.LAB_PRACTICAL]:
                attrs["exam_duration_per_student_minutes"] = None
                if "exam_duration_minutes" in attrs:
                    if not attrs["exam_duration_minutes"]:
                        attrs["exam_duration_minutes"] = 120
                elif self.instance and not self.instance.exam_duration_minutes:
                    attrs["exam_duration_minutes"] = 120

            if is_eo:
                return attrs

        owning_level = attrs.get("owning_level", self.instance.owning_level if self.instance else None)
        owning_dept = attrs.get("owning_department", self.instance.owning_department if self.instance else None)
        owning_fac = attrs.get("owning_faculty", self.instance.owning_faculty if self.instance else None)
        owning_sch = attrs.get("owning_school", self.instance.owning_school if self.instance else None)
        program_scope = attrs.get("program_scope", self.instance.program_scope if self.instance else Course.ProgramScope.GENERAL)
        target_prog = attrs.get("target_program", self.instance.target_program if self.instance else None)

        # Validate that only matching ownership field is set
        if owning_level == Course.OwningLevel.DEPARTMENT and not owning_dept:
            raise serializers.ValidationError({"owning_department": "owning_department is required for department-owned course."})
        if owning_level == Course.OwningLevel.FACULTY and not owning_fac:
            raise serializers.ValidationError({"owning_faculty": "owning_faculty is required for faculty-owned course."})
        if owning_level == Course.OwningLevel.SCHOOL and not owning_sch:
            raise serializers.ValidationError({"owning_school": "owning_school is required for school-owned course."})

        # Program scope validation
        if program_scope == Course.ProgramScope.PROGRAM:
            if not target_prog:
                raise serializers.ValidationError({"target_program": "target_program is required when program_scope is 'program'."})
            if owning_dept and target_prog.department_id != owning_dept.id:
                raise serializers.ValidationError({"target_program": "target_program must belong to the course's owning department."})
        elif program_scope == Course.ProgramScope.GENERAL:
            attrs["target_program"] = None

        # Creation-time ownership guardrails based on requesting admin's level
        if (user.role in ["admin", "system_admin"] or user.is_superuser) and hasattr(user, "admin_profile"):
            admin_prof = user.admin_profile
            if admin_prof.level in ["system", "university"]:
                raise serializers.ValidationError("System level admins have view-only access and cannot create or edit courses.")

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
    target_program_name = serializers.ReadOnlyField(source="target_program.name")
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
            "grant_scope",
            "target_program",
            "target_program_name",
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

    def validate(self, attrs):
        grant_scope = attrs.get("grant_scope", self.instance.grant_scope if self.instance else CourseAccessGrant.GrantScope.GENERAL)
        target_prog = attrs.get("target_program", self.instance.target_program if self.instance else None)
        granted_dept = attrs.get("granted_to_department", self.instance.granted_to_department if self.instance else None)

        if grant_scope == CourseAccessGrant.GrantScope.PROGRAM:
            if not target_prog:
                raise serializers.ValidationError({"target_program": "target_program is required when grant_scope is 'program'."})
            if granted_dept and target_prog.department_id != granted_dept.id:
                raise serializers.ValidationError({"target_program": "target_program must belong to the granted department."})
        elif grant_scope == CourseAccessGrant.GrantScope.GENERAL:
            attrs["target_program"] = None

        return attrs


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
