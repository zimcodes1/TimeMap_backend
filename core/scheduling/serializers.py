import datetime
from django.utils import timezone
from accounts.models import AdminOfficer
from courses.models import CourseRegistration
from discrepancies.models import DiscrepancyRequest
from rest_framework import serializers

from .conflict_engine import check_student_exam_clash, determine_booking_routing
from .models import (
    AcademicSession,
    ExamSitting,
    FacultyExamPeriod,
    GenerationScopePermission,
    LectureSession,
    Semester,
    TimetableEntry,
    TimetableGenerationRun,
)
from .services import get_effective_exam_period, materialize_timetable_entry


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

        # Validate name against session's configured max_semesters
        name = attrs.get("name", self.instance.name if self.instance else None)
        if session and name:
            max_allowed = getattr(session, "max_semesters", 2) or 2
            ordinal_map = {"first": 1, "second": 2, "third": 3, "fourth": 4}
            ordinal = ordinal_map.get(name)
            if ordinal and ordinal > max_allowed:
                raise serializers.ValidationError({
                    "name": f"'{name.capitalize()} Semester' is not permitted because session '{session.label}' only allows up to {max_allowed} semesters."
                })

            if not self.instance:
                current_count = session.semesters.count()
                if current_count >= max_allowed:
                    raise serializers.ValidationError({
                        "session": f"Session '{session.label}' has already reached its maximum of {max_allowed} semesters."
                    })

        # Mandatory lecture start and end dates
        lecture_start = attrs.get("lecture_start_date", self.instance.lecture_start_date if self.instance else None)
        lecture_end = attrs.get("lecture_end_date", self.instance.lecture_end_date if self.instance else None)
        start_date = attrs.get("start_date", self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date", self.instance.end_date if self.instance else None)

        if not lecture_start or not lecture_end:
            raise serializers.ValidationError({
                "lecture_start_date": "Lecture start and end dates are required to define the teaching calendar.",
                "lecture_end_date": "Lecture start and end dates are required to define the teaching calendar.",
            })

        if lecture_start >= lecture_end:
            raise serializers.ValidationError({
                "lecture_end_date": "Lecture end date must be after lecture start date."
            })

        if start_date and lecture_start < start_date:
            raise serializers.ValidationError({
                "lecture_start_date": "Lecture start date cannot be before semester start date."
            })

        if end_date and lecture_end > end_date:
            raise serializers.ValidationError({
                "lecture_end_date": "Lecture end date cannot be after semester end date."
            })

        exam_start = attrs.get("exam_start_date", self.instance.exam_start_date if self.instance else None)
        exam_end = attrs.get("exam_end_date", self.instance.exam_end_date if self.instance else None)
        if exam_start and exam_end:
            if exam_start >= exam_end:
                raise serializers.ValidationError({
                    "exam_end_date": "Exam end date must be after exam start date."
                })
            if start_date and exam_start < start_date:
                raise serializers.ValidationError({
                    "exam_start_date": "Exam start date cannot be before semester start date."
                })
            if end_date and exam_end > end_date:
                raise serializers.ValidationError({
                    "exam_end_date": "Exam end date cannot be after semester end date."
                })

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
            "max_semesters",
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

        max_semesters = attrs.get("max_semesters")
        if max_semesters is not None:
            if max_semesters < 1 or max_semesters > 6:
                raise serializers.ValidationError({"max_semesters": "Max semesters per session must be between 1 and 6."})
            if self.instance and self.instance.semesters.count() > max_semesters:
                raise serializers.ValidationError({
                    "max_semesters": f"Cannot set max semesters to {max_semesters} because this session already has {self.instance.semesters.count()} semesters."
                })

        return attrs


from hierarchy.models import Program

class TimetableEntrySerializer(serializers.ModelSerializer):
    target_program = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(), required=False, allow_null=True
    )
    target_level = serializers.IntegerField(required=False, allow_null=True)
    course_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    course_level = serializers.SerializerMethodField()
    course_type = serializers.ReadOnlyField(source="course.course_type")
    department_id = serializers.ReadOnlyField(source="course.owning_department_id")
    department_name = serializers.ReadOnlyField(source="course.owning_department.name")
    faculty_id = serializers.ReadOnlyField(source="course.owning_department.faculty_id")
    faculty_name = serializers.ReadOnlyField(source="course.owning_department.faculty.name")
    target_program_id = serializers.SerializerMethodField()
    target_program_name = serializers.SerializerMethodField()
    program_scope = serializers.ReadOnlyField(source="course.program_scope")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    venue_capacity = serializers.ReadOnlyField(source="venue.capacity")
    created_by_name = serializers.ReadOnlyField(source="created_by.full_name")
    semester_name = serializers.ReadOnlyField(source="semester.get_name_display")
    session_label = serializers.ReadOnlyField(source="semester.session.label")
    day_of_week = serializers.SerializerMethodField()
    lecturer_name = serializers.SerializerMethodField()
    lecturers = serializers.SerializerMethodField()
    expected_students = serializers.SerializerMethodField()
    has_conflict = serializers.SerializerMethodField()
    conflict_reason = serializers.SerializerMethodField()

    class Meta:
        model = TimetableEntry
        fields = (
            "id",
            "entry_type",
            "title",
            "course",
            "course_code",
            "course_title",
            "course_level",
            "course_type",
            "department_id",
            "department_name",
            "faculty_id",
            "faculty_name",
            "target_program",
            "target_program_id",
            "target_program_name",
            "target_level",
            "program_scope",
            "venue",
            "venue_name",
            "venue_capacity",
            "day_of_week",
            "start_time",
            "end_time",
            "lecturer_name",
            "lecturers",
            "expected_students",
            "has_conflict",
            "conflict_reason",
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

    def get_course_code(self, obj) -> str:
        if obj.course:
            return obj.course.code
        return "EVENT" if obj.entry_type == "event" else ""

    def get_course_title(self, obj) -> str:
        if obj.course:
            return obj.course.title
        return obj.title or ("Event" if obj.entry_type == "event" else "")

    def get_course_level(self, obj) -> int | None:
        if obj.course:
            return obj.course.level
        return obj.target_level

    def get_target_program_id(self, obj) -> str | None:
        if obj.course and obj.course.target_program_id:
            return str(obj.course.target_program_id)
        if obj.target_program_id:
            return str(obj.target_program_id)
        return None

    def get_target_program_name(self, obj) -> str | None:
        if obj.course and obj.course.target_program:
            return obj.course.target_program.name
        if obj.target_program:
            return obj.target_program.name
        return None

    def _get_conflict_info(self, obj):
        if hasattr(obj, "_cached_conflict_info"):
            return obj._cached_conflict_info

        info = {"has_conflict": False, "reason": ""}
        if not obj.venue_id or not obj.recurrence_rule:
            obj._cached_conflict_info = info
            return info

        # 1. Venue collision
        venue_clash = (
            TimetableEntry.objects.filter(
                semester_id=obj.semester_id,
                recurrence_rule=obj.recurrence_rule,
                venue_id=obj.venue_id,
                start_time__lt=obj.end_time,
                end_time__gt=obj.start_time,
            )
            .exclude(id=obj.id)
            .select_related("course")
            .first()
        )
        if venue_clash and venue_clash.course:
            info["has_conflict"] = True
            venue_label = obj.venue.name if obj.venue else "Venue"
            info["reason"] = f"Venue collision with {venue_clash.course.code} at {venue_label}"
            obj._cached_conflict_info = info
            return info

        # 2. Lecturer collision
        if obj.course:
            lecs = obj.course.lecturers.all()
            if lecs:
                lec_clash = (
                    TimetableEntry.objects.filter(
                        semester_id=obj.semester_id,
                        recurrence_rule=obj.recurrence_rule,
                        course__lecturers__in=lecs,
                        start_time__lt=obj.end_time,
                        end_time__gt=obj.start_time,
                    )
                    .exclude(id=obj.id)
                    .select_related("course")
                    .first()
                )
                if lec_clash and lec_clash.course:
                    lec_name = lecs[0].full_name
                    info["has_conflict"] = True
                    info["reason"] = f"Lecturer collision: {lec_name} is double-booked with {lec_clash.course.code}"
                    obj._cached_conflict_info = info
                    return info

        obj._cached_conflict_info = info
        return info

    def get_has_conflict(self, obj) -> bool:
        return self._get_conflict_info(obj)["has_conflict"]

    def get_conflict_reason(self, obj) -> str:
        return self._get_conflict_info(obj)["reason"]

    def get_day_of_week(self, obj) -> str:
        if obj.recurrence_rule and ":" in obj.recurrence_rule:
            return obj.recurrence_rule.split(":")[-1].strip().capitalize()
        if obj.recurrence_start_date:
            return obj.recurrence_start_date.strftime("%A")
        return "Monday"

    def get_lecturer_name(self, obj) -> str:
        if not obj.course:
            return ""
        first_lec = obj.course.lecturers.first()
        return first_lec.full_name if first_lec else ""

    def get_lecturers(self, obj) -> list:
        if not obj.course:
            return []
        return [l.full_name for l in obj.course.lecturers.all()]

    def get_expected_students(self, obj) -> int:
        if not obj.course:
            return 50
        try:
            from student_counts.models import ProgramStudentCount
            if obj.course.target_program_id:
                sc = ProgramStudentCount.objects.filter(
                    program_id=obj.course.target_program_id,
                    level=obj.course.level,
                ).first()
                if sc:
                    return sc.count
            elif obj.course.owning_department_id:
                counts = list(
                    ProgramStudentCount.objects.filter(
                        program__department_id=obj.course.owning_department_id,
                        level=obj.course.level,
                    ).values_list("count", flat=True)
                )
                if counts:
                    return sum(counts)
        except Exception:
            pass
        return 50

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

            if entry_type == "lecture" and recurrence_rule:
                if semester:
                    l_start = semester.lecture_start_date or semester.start_date
                    l_end = semester.lecture_end_date or semester.end_date
                    if not recurrence_start_date or recurrence_start_date < l_start:
                        attrs["recurrence_start_date"] = l_start
                        recurrence_start_date = l_start
                    if not recurrence_end_date or recurrence_end_date > l_end:
                        attrs["recurrence_end_date"] = l_end
                        recurrence_end_date = l_end

            elif entry_type == "event":
                title = attrs.get("title", self.instance.title if self.instance else None)
                if not title:
                    raise serializers.ValidationError({"title": "Event title or name is required."})
                event_date = recurrence_start_date or attrs.get("start_date")
                if not event_date:
                    raise serializers.ValidationError({"recurrence_start_date": "Event date is required."})
                if isinstance(event_date, str):
                    try:
                        event_date = datetime.date.fromisoformat(event_date)
                    except ValueError:
                        pass
                if isinstance(event_date, (datetime.date, datetime.datetime)):
                    if isinstance(event_date, datetime.datetime):
                        event_date = event_date.date()
                    if event_date < datetime.date.today():
                        raise serializers.ValidationError({"recurrence_start_date": "An event's date cannot be in the past."})
                attrs["recurrence_start_date"] = event_date
                attrs["recurrence_end_date"] = event_date
                attrs["recurrence_rule"] = None

            elif entry_type == "exam":
                if not semester:
                    raise serializers.ValidationError({"semester": "An active semester is required for exam scheduling."})
                faculty = None
                department = None
                if course:
                    faculty = course.owning_faculty
                    department = course.owning_department
                    if not faculty and department:
                        faculty = department.faculty

                exam_start, exam_end, source, _ = get_effective_exam_period(semester, faculty=faculty, department=department)
                if not exam_start or not exam_end:
                    raise serializers.ValidationError({
                        "detail": "Examination timetable cannot be scheduled because the examination period has not been defined by the administrator."
                    })

                exam_date = recurrence_start_date or attrs.get("start_date")
                if not exam_date:
                    attrs["recurrence_start_date"] = exam_start
                    exam_date = exam_start
                    recurrence_start_date = exam_start
                else:
                    if exam_date < exam_start or exam_date > exam_end:
                        raise serializers.ValidationError({
                            "recurrence_start_date": f"Exam date ({exam_date}) must fall within the defined examination period ({exam_start} to {exam_end})."
                        })
                if not recurrence_end_date:
                    attrs["recurrence_end_date"] = exam_date
                    recurrence_end_date = exam_date

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

            # Stage the entry in the database with PENDING_APPROVAL status
            validated_data["status"] = TimetableEntry.Status.PENDING_APPROVAL
            entry = super().create(validated_data)

            routed_to_id = routing_info.get("routed_to_admin_id")
            if not routed_to_id:
                try:
                    from discrepancies.services import resolve_discrepancy_routing_admin
                    target_admin = resolve_discrepancy_routing_admin(entry.venue)
                    if target_admin:
                        routed_to_id = target_admin.id
                except Exception:
                    pass

            discrepancy = DiscrepancyRequest.objects.create(
                timetable_entry=entry,
                request_type=DiscrepancyRequest.RequestType.CREATE_BOOKING,
                proposed_venue=entry.venue,
                proposed_start_time=entry.start_time,
                proposed_end_time=entry.end_time,
                proposed_date=entry.recurrence_start_date,
                reason=f"Booking request for '{entry.title}' against cross-level venue",
                initiated_by=user,
                routed_to_id=routed_to_id,
                status=DiscrepancyRequest.Status.PENDING,
            )

            # Dispatch in-app notification to routed admin officer
            if routed_to_id:
                try:
                    routed_admin = AdminOfficer.objects.filter(id=routed_to_id).first()
                    if routed_admin and routed_admin.user:
                        from notifications.models import Notification
                        from notifications.services import dispatch_event_notification
                        venue_name = entry.venue.name if entry.venue else "a venue"
                        dispatch_event_notification(
                            recipient=routed_admin.user,
                            notification_type=Notification.NotificationType.DISCREPANCY_SUBMITTED,
                            title="New Discrepancy Request Pending Approval",
                            body=f"Booking request for '{entry.title}' in venue '{venue_name}' has been routed to you for approval.",
                            related_model="DiscrepancyRequest",
                            related_id=discrepancy.id,
                        )
                except Exception as notif_err:
                    import logging
                    logging.getLogger(__name__).warning("Failed to dispatch discrepancy notification: %s", notif_err)

            # Attach discrepancy reference to serializer context/attribute
            self.context["pending_discrepancy"] = discrepancy
            return entry

        entry = super().create(validated_data)

        # Trigger materialization automatically if it's a recurring lecture
        if entry.entry_type == TimetableEntry.EntryType.LECTURE and entry.recurrence_rule:
            materialize_timetable_entry(entry)

        # Automatically materialize exam session and sitting if it's an exam entry
        elif entry.entry_type == TimetableEntry.EntryType.EXAM and entry.recurrence_start_date:
            session_date = entry.recurrence_start_date
            LectureSession.objects.get_or_create(
                timetable_entry=entry,
                session_date=session_date,
                defaults={
                    "session_start_time": entry.start_time,
                    "session_end_time": entry.end_time,
                    "venue": entry.venue,
                    "status": LectureSession.Status.SCHEDULED,
                },
            )
            ExamSitting.objects.get_or_create(
                timetable_entry=entry,
                defaults={"registered_candidates_count": 0},
            )

        # Automatically materialize event session and shift conflicting sessions
        elif entry.entry_type == TimetableEntry.EntryType.EVENT and entry.recurrence_start_date:
            session_date = entry.recurrence_start_date
            overlapping_sessions = LectureSession.objects.filter(
                venue=entry.venue,
                session_date=session_date,
                session_start_time__lt=entry.end_time,
                session_end_time__gt=entry.start_time,
            ).exclude(timetable_entry=entry)
            overlapping_sessions.update(status=LectureSession.Status.SHIFTED)

            LectureSession.objects.get_or_create(
                timetable_entry=entry,
                session_date=session_date,
                defaults={
                    "session_start_time": entry.start_time,
                    "session_end_time": entry.end_time,
                    "venue": entry.venue,
                    "status": LectureSession.Status.SCHEDULED,
                },
            )

        return entry


class LectureSessionSerializer(serializers.ModelSerializer):
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    entry_type = serializers.ReadOnlyField(source="timetable_entry.entry_type")
    course_id = serializers.ReadOnlyField(source="timetable_entry.course_id")
    course_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    course_level = serializers.SerializerMethodField()
    department_id = serializers.ReadOnlyField(source="timetable_entry.course.owning_department_id")
    department_name = serializers.ReadOnlyField(source="timetable_entry.course.owning_department.name")
    target_program_id = serializers.SerializerMethodField()
    program_name = serializers.SerializerMethodField()
    program_code = serializers.SerializerMethodField()
    program_scope = serializers.ReadOnlyField(source="timetable_entry.course.program_scope")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    venue_capacity = serializers.ReadOnlyField(source="venue.capacity")
    day_of_week = serializers.SerializerMethodField()
    lecturer_name = serializers.SerializerMethodField()
    lecturers = serializers.SerializerMethodField()
    can_shift = serializers.SerializerMethodField()
    report_status = serializers.SerializerMethodField()
    report_window_open = serializers.SerializerMethodField()
    report_window_expires_at = serializers.SerializerMethodField()
    report_id = serializers.SerializerMethodField()
    has_conflict = serializers.SerializerMethodField()
    conflict_reason = serializers.SerializerMethodField()

    class Meta:
        model = LectureSession
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "entry_type",
            "course_id",
            "course_code",
            "course_title",
            "course_level",
            "department_id",
            "department_name",
            "target_program_id",
            "program_name",
            "program_code",
            "program_scope",
            "session_date",
            "session_start_time",
            "session_end_time",
            "day_of_week",
            "venue",
            "venue_name",
            "venue_capacity",
            "lecturer_name",
            "lecturers",
            "has_conflict",
            "conflict_reason",
            "status",
            "can_shift",
            "report_status",
            "report_window_open",
            "report_window_expires_at",
            "report_id",
        )
        read_only_fields = ("id",)

    def get_course_code(self, obj) -> str:
        te = obj.timetable_entry
        if te and te.course:
            return te.course.code
        return "EVENT" if (te and te.entry_type == "event") else ""

    def get_course_title(self, obj) -> str:
        te = obj.timetable_entry
        if te and te.course:
            return te.course.title
        if te and te.title:
            return te.title
        return "Event" if (te and te.entry_type == "event") else ""

    def get_course_level(self, obj) -> int | None:
        te = obj.timetable_entry
        if te and te.course:
            return te.course.level
        return te.target_level if te else None

    def get_target_program_id(self, obj) -> str | None:
        te = obj.timetable_entry
        if te and te.course and te.course.target_program_id:
            return str(te.course.target_program_id)
        if te and te.target_program_id:
            return str(te.target_program_id)
        return None

    def get_program_name(self, obj) -> str | None:
        te = obj.timetable_entry
        if te and te.course and te.course.target_program:
            return te.course.target_program.name
        if te and te.target_program:
            return te.target_program.name
        return None

    def get_program_code(self, obj) -> str | None:
        te = obj.timetable_entry
        if te and te.course and te.course.target_program:
            return te.course.target_program.code
        if te and te.target_program:
            return te.target_program.code
        return None

    def get_report_id(self, obj) -> str | None:
        try:
            if hasattr(obj, "report") and obj.report:
                return str(obj.report.id)
        except Exception:
            pass
        return None

    def get_report_window_expires_at(self, obj) -> str | None:
        try:
            tz = timezone.get_current_timezone()
            dt = datetime.datetime.combine(obj.session_date, obj.session_end_time)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, tz)
            expiry = dt + datetime.timedelta(minutes=30)
            return expiry.isoformat()
        except Exception:
            return None

    def get_report_window_open(self, obj) -> bool:
        if self.get_report_id(obj):
            return False
        try:
            tz = timezone.get_current_timezone()
            now = timezone.now()
            start_dt = datetime.datetime.combine(obj.session_date, obj.session_start_time)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt, tz)

            end_dt = datetime.datetime.combine(obj.session_date, obj.session_end_time)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt, tz)

            expiry_dt = end_dt + datetime.timedelta(minutes=30)
            return start_dt <= now <= expiry_dt
        except Exception:
            return False

    def get_has_conflict(self, obj) -> bool:
        if obj.timetable_entry:
            return TimetableEntrySerializer().get_has_conflict(obj.timetable_entry)
        return False

    def get_conflict_reason(self, obj) -> str:
        if obj.timetable_entry:
            return TimetableEntrySerializer().get_conflict_reason(obj.timetable_entry)
        return ""

    def get_day_of_week(self, obj) -> str:
        if obj.session_date:
            return obj.session_date.strftime("%A")
        return "Monday"

    def get_lecturer_name(self, obj) -> str:
        course = getattr(obj.timetable_entry, "course", None)
        if not course:
            return ""
        first_lec = course.lecturers.first()
        return first_lec.full_name if first_lec else ""

    def get_lecturers(self, obj) -> list:
        course = getattr(obj.timetable_entry, "course", None)
        if not course:
            return []
        return [
            {
                "id": str(l.id),
                "name": l.full_name,
                "full_name": l.full_name,
                "staff_id": l.staff_id,
                "email": l.email or "",
            }
            for l in course.lecturers.all()
        ]

    def get_can_shift(self, obj) -> bool:
        # Past sessions can NEVER be shifted
        now = timezone.now()
        dt = datetime.datetime.combine(obj.session_date, obj.session_end_time)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        if dt <= now:
            return False

        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        if user.is_superuser:
            return True
        admin_profile = getattr(user, "admin_profile", None)
        if not admin_profile:
            return False

        from accounts.models import AdminOfficer
        if admin_profile.level == AdminOfficer.Level.SCHOOL:
            return True

        course = getattr(obj.timetable_entry, "course", None)
        if not course:
            return obj.timetable_entry.created_by_id == admin_profile.id

        if admin_profile.level == AdminOfficer.Level.FACULTY and admin_profile.scope_faculty_id:
            dept = getattr(course, "owning_department", None)
            if dept and dept.faculty_id == admin_profile.scope_faculty_id:
                return True

        if admin_profile.level == AdminOfficer.Level.DEPARTMENT and admin_profile.scope_department_id:
            if course.owning_department_id == admin_profile.scope_department_id:
                return True

        return obj.timetable_entry.created_by_id == admin_profile.id

    def get_report_status(self, obj) -> str:
        try:
            report = obj.report
            return "held" if report.held else "not_held"
        except Exception:
            pass

        if obj.status == LectureSession.Status.HELD:
            return "held"
        if obj.status == LectureSession.Status.NOT_HELD:
            return "not_held"

        # A schedule isn't unreported until after the datetime for it has past
        now = timezone.now()
        dt = datetime.datetime.combine(obj.session_date, obj.session_end_time)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)

        if dt <= now:
            return "unreported"
        return "scheduled"


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


class GenerationScopePermissionSerializer(serializers.ModelSerializer):
    school_name = serializers.ReadOnlyField(source="school.name")
    school_code = serializers.ReadOnlyField(source="school.code")

    class Meta:
        model = GenerationScopePermission
        fields = (
            "id",
            "school",
            "school_name",
            "school_code",
            "allow_faculty_generation",
            "allow_department_generation",
            "allow_faculty_exam_period",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class FacultyExamPeriodSerializer(serializers.ModelSerializer):
    faculty_name = serializers.ReadOnlyField(source="faculty.name")
    faculty_code = serializers.ReadOnlyField(source="faculty.code")
    semester_name = serializers.ReadOnlyField(source="semester.get_name_display")

    class Meta:
        model = FacultyExamPeriod
        fields = (
            "id",
            "semester",
            "semester_name",
            "faculty",
            "faculty_name",
            "faculty_code",
            "start_date",
            "end_date",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate(self, attrs):
        semester = attrs.get("semester", self.instance.semester if self.instance else None)
        faculty = attrs.get("faculty", self.instance.faculty if self.instance else None)
        start_date = attrs.get("start_date", self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date", self.instance.end_date if self.instance else None)

        if not semester:
            raise serializers.ValidationError({"semester": "Semester is required."})
        if not faculty:
            raise serializers.ValidationError({"faculty": "Faculty is required."})

        school = semester.session.school if semester.session else None
        if not school or faculty.school_id != school.id:
            raise serializers.ValidationError({"faculty": "Faculty does not belong to the semester's school."})

        perm = GenerationScopePermission.objects.filter(school=school).first()
        if not perm or not perm.allow_faculty_exam_period:
            raise serializers.ValidationError({
                "detail": "Faculty-level exam periods are disabled by the school administrator."
            })

        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError({"end_date": "Exam period end date must be after start date."})

        if semester.start_date and start_date and start_date < semester.start_date:
            raise serializers.ValidationError({"start_date": "Exam period cannot start before semester start date."})

        if semester.end_date and end_date and end_date > semester.end_date:
            raise serializers.ValidationError({"end_date": "Exam period cannot end after semester end date."})

        return attrs


class TimetableGenerationRunSerializer(serializers.ModelSerializer):
    semester_name = serializers.ReadOnlyField(source="semester.get_name_display")
    session_label = serializers.ReadOnlyField(source="semester.session.label")
    school_id = serializers.ReadOnlyField(source="semester.session.school.id")
    school_name = serializers.ReadOnlyField(source="semester.session.school.name")
    initiated_by_name = serializers.ReadOnlyField(source="initiated_by.identifier")

    class Meta:
        model = TimetableGenerationRun
        fields = (
            "id",
            "semester",
            "semester_name",
            "session_label",
            "school_id",
            "school_name",
            "scope_type",
            "scope_id",
            "scope_name",
            "status",
            "result_status",
            "hard_conflicts_count",
            "student_conflicts_count",
            "lecturer_conflicts_count",
            "venue_conflicts_count",
            "daily_limit_violations_count",
            "occurrence_day_violations_count",
            "capacity_penalty",
            "fitness_score",
            "generation_metrics",
            "is_published",
            "initiated_by",
            "initiated_by_name",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields


class TimetableGenerationRunDetailSerializer(TimetableGenerationRunSerializer):
    class Meta(TimetableGenerationRunSerializer.Meta):
        fields = TimetableGenerationRunSerializer.Meta.fields + (
            "conflict_report",
            "assignments_payload",
        )


class GenerateTimetableRequestSerializer(serializers.Serializer):
    semester_id = serializers.IntegerField(required=False)
    semester = serializers.IntegerField(required=False)
    scope_type = serializers.ChoiceField(
        choices=["school", "faculty", "department"], required=True
    )
    scope_id = serializers.IntegerField(required=True)
    population_size = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=10, max_value=500
    )
    max_generations = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=10, max_value=2000
    )
    mutation_rate = serializers.FloatField(
        required=False, allow_null=True, default=None, min_value=0.01, max_value=1.0
    )
    stagnation_limit = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=5, max_value=300
    )
    publish_immediately = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if not attrs.get("semester_id") and not attrs.get("semester"):
            raise serializers.ValidationError({"semester_id": "Either semester_id or semester is required."})
        if not attrs.get("semester_id"):
            attrs["semester_id"] = attrs["semester"]
        if not attrs.get("semester"):
            attrs["semester"] = attrs["semester_id"]
        return attrs

