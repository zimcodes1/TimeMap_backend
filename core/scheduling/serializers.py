from courses.models import CourseRegistration
from discrepancies.models import DiscrepancyRequest
from rest_framework import serializers

from .conflict_engine import check_student_exam_clash, determine_booking_routing
from .models import AcademicSession, ExamSitting, LectureSession, Semester, TimetableEntry
from .services import materialize_timetable_entry


class SemesterSerializer(serializers.ModelSerializer):
    session_label = serializers.ReadOnlyField(source="session.label")
    school_id = serializers.ReadOnlyField(source="session.school.id")
    school_name = serializers.ReadOnlyField(source="session.school.name")
    created_by_name = serializers.ReadOnlyField(source="created_by.full_name")

    class Meta:
        model = Semester
        fields = (
            "id",
            "session",
            "session_label",
            "school_id",
            "school_name",
            "name",
            "start_date",
            "end_date",
            "duration_type",
            "duration_value",
            "lecture_start_date",
            "lecture_end_date",
            "exam_start_date",
            "exam_end_date",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_by_name", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        session = attrs.get("session", self.instance.session if self.instance else None)
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
                if hasattr(user, "admin_profile") and user.admin_profile.level == "school":
                    if session and user.admin_profile.scope_school_id and session.school_id != user.admin_profile.scope_school_id:
                        raise serializers.ValidationError({"session": "School admins can only manage semesters within their assigned school."})
        return attrs


class AcademicSessionSerializer(serializers.ModelSerializer):
    school_name = serializers.ReadOnlyField(source="school.name")
    school_code = serializers.ReadOnlyField(source="school.code")
    semesters = SemesterSerializer(many=True, read_only=True)

    class Meta:
        model = AcademicSession
        fields = (
            "id",
            "school",
            "school_name",
            "school_code",
            "label",
            "start_date",
            "end_date",
            "is_current",
            "semesters",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        school = attrs.get("school", self.instance.school if self.instance else None)
        if request and request.user and request.user.is_authenticated:
            user = request.user
            if not (user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile"))):
                if hasattr(user, "admin_profile") and user.admin_profile.level == "school":
                    if school and user.admin_profile.scope_school_id and school.id != user.admin_profile.scope_school_id:
                        raise serializers.ValidationError({"school": "School admins can only create sessions for their assigned school."})
        return attrs


class TimetableEntrySerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="course.code")
    course_level = serializers.ReadOnlyField(source="course.level")
    target_program_id = serializers.ReadOnlyField(source="course.target_program_id")
    target_program_name = serializers.ReadOnlyField(source="course.target_program.name")
    program_scope = serializers.ReadOnlyField(source="course.program_scope")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    created_by_name = serializers.ReadOnlyField(source="created_by.full_name")
    semester_name = serializers.ReadOnlyField(source="semester.get_name_display")
    session_label = serializers.ReadOnlyField(source="semester.session.label")

    class Meta:
        model = TimetableEntry
        fields = (
            "id",
            "entry_type",
            "title",
            "course",
            "course_code",
            "course_level",
            "target_program_id",
            "target_program_name",
            "program_scope",
            "venue",
            "venue_name",
            "start_time",
            "end_time",
            "recurrence_rule",
            "recurrence_start_date",
            "recurrence_end_date",
            "status",
            "created_by",
            "created_by_name",
            "semester",
            "semester_name",
            "session_label",
            "academic_session",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            venue = attrs.get("venue", self.instance.venue if self.instance else None)
            start_time = attrs.get("start_time", self.instance.start_time if self.instance else None)
            end_time = attrs.get("end_time", self.instance.end_time if self.instance else None)
            entry_type = attrs.get("entry_type", self.instance.entry_type if self.instance else "lecture")
            course = attrs.get("course", self.instance.course if self.instance else None)
            semester = attrs.get("semester", self.instance.semester if self.instance else None)
            if semester and not attrs.get("academic_session"):
                attrs["academic_session"] = semester.session.label
            academic_session = attrs.get("academic_session", self.instance.academic_session if self.instance else "2025/2026")
            recurrence_rule = attrs.get("recurrence_rule", self.instance.recurrence_rule if self.instance else None)
            recurrence_start_date = attrs.get("recurrence_start_date", self.instance.recurrence_start_date if self.instance else None)
            recurrence_end_date = attrs.get("recurrence_end_date", self.instance.recurrence_end_date if self.instance else None)

            date_or_start = recurrence_start_date

            if venue and start_time and end_time and date_or_start:
                exclude_id = self.instance.id if self.instance else None
                routing = determine_booking_routing(
                    user=request.user,
                    venue=venue,
                    date_or_start_date=date_or_start,
                    start_time=start_time,
                    end_time=end_time,
                    entry_type=entry_type,
                    course=course,
                    academic_session=academic_session,
                    recurrence_rule=recurrence_rule,
                    recurrence_end_date=recurrence_end_date,
                    exclude_entry_id=exclude_id,
                )

                if routing["outcome"] == "HARD_REJECT":
                    raise serializers.ValidationError({
                        "detail": routing["message"],
                        "conflicts": routing["conflicts"],
                    })

                attrs["_routing_info"] = routing

        return attrs

    def create(self, validated_data):
        routing_info = validated_data.pop("_routing_info", None)

        if routing_info and routing_info.get("outcome") == "ROUTE_APPROVAL":
            request = self.context.get("request")
            user = request.user if request else None

            discrepancy = DiscrepancyRequest.objects.create(
                request_type=DiscrepancyRequest.RequestType.CREATE_BOOKING,
                proposed_venue=validated_data.get("venue"),
                proposed_start_time=validated_data.get("start_time"),
                proposed_date=validated_data.get("recurrence_start_date"),
                reason=f"Booking request for '{validated_data.get('title')}' against cross-level venue",
                initiated_by=user,
                routed_to_id=routing_info.get("routed_to_admin_id"),
                status=DiscrepancyRequest.Status.PENDING,
            )
            # Attach discrepancy reference to serializer context/attribute
            self.context["pending_discrepancy"] = discrepancy
            # Return dummy unsaved/placeholder entry object or marker
            entry = TimetableEntry(**validated_data)
            entry.id = None
            return entry

        entry = super().create(validated_data)

        # Trigger materialization automatically if it's a recurring lecture
        if entry.entry_type == TimetableEntry.EntryType.LECTURE and entry.recurrence_rule:
            materialize_timetable_entry(entry)

        return entry


class LectureSessionSerializer(serializers.ModelSerializer):
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    entry_type = serializers.ReadOnlyField(source="timetable_entry.entry_type")
    course_code = serializers.ReadOnlyField(source="timetable_entry.course.code")
    course_title = serializers.ReadOnlyField(source="timetable_entry.course.title")
    course_level = serializers.ReadOnlyField(source="timetable_entry.course.level")
    department_name = serializers.ReadOnlyField(source="timetable_entry.course.owning_department.name")
    target_program_id = serializers.ReadOnlyField(source="timetable_entry.course.target_program_id")
    program_name = serializers.ReadOnlyField(source="timetable_entry.course.target_program.name")
    program_code = serializers.ReadOnlyField(source="timetable_entry.course.target_program.code")
    program_scope = serializers.ReadOnlyField(source="timetable_entry.course.program_scope")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    can_shift = serializers.SerializerMethodField()
    report_status = serializers.SerializerMethodField()

    class Meta:
        model = LectureSession
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "entry_type",
            "course_code",
            "course_title",
            "course_level",
            "department_name",
            "target_program_id",
            "program_name",
            "program_code",
            "program_scope",
            "session_date",
            "session_start_time",
            "session_end_time",
            "venue",
            "venue_name",
            "status",
            "can_shift",
            "report_status",
        )
        read_only_fields = ("id",)

    def get_can_shift(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        if user.is_superuser:
            return True
        admin_profile = getattr(user, "admin_profile", None)
        if not admin_profile:
            return False
        return obj.timetable_entry.created_by_id == admin_profile.id

    def get_report_status(self, obj) -> str:
        try:
            report = obj.report
            return "held" if report.held else "not_held"
        except Exception:
            return "unreported"


class ExamSittingSerializer(serializers.ModelSerializer):
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    course_code = serializers.ReadOnlyField(source="timetable_entry.course.code")
    registered_candidates_count = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = ExamSitting
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "course_code",
            "registered_candidates_count",
            "invigilators",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        request = self.context.get("request")
        entry = attrs.get("timetable_entry", self.instance.timetable_entry if self.instance else None)
        invigilator_objs = attrs.get("invigilators", [])
        invigilator_ids = [inv.id for inv in invigilator_objs] if invigilator_objs else []

        if entry and entry.recurrence_start_date and entry.start_time and entry.end_time:
            # Check student exam clashes
            student_clashes = check_student_exam_clash(
                course=entry.course,
                date=entry.recurrence_start_date,
                start_time=entry.start_time,
                end_time=entry.end_time,
                academic_session=entry.academic_session,
                exclude_entry_id=entry.id,
            )

            if student_clashes:
                raise serializers.ValidationError({
                    "detail": "Student exam conflict detected.",
                    "conflicts": student_clashes,
                })

        return attrs

    def create(self, validated_data):
        entry = validated_data.get("timetable_entry")
        # Auto calculate registered candidates count if not provided
        if "registered_candidates_count" not in validated_data or validated_data["registered_candidates_count"] is None:
            if entry and entry.course:
                count = CourseRegistration.objects.filter(
                    course=entry.course, academic_session=entry.academic_session
                ).count()
                validated_data["registered_candidates_count"] = count
            else:
                validated_data["registered_candidates_count"] = 0

        return super().create(validated_data)
