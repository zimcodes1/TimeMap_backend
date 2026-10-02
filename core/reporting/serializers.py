from rest_framework import serializers

from .models import ClassRepReport, UnreportedSessionFlag
from .services import create_class_rep_report


class ClassRepReportSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.ReadOnlyField(source="reported_by.full_name")
    course_code = serializers.ReadOnlyField(source="lecture_session.timetable_entry.course.code")
    course_title = serializers.ReadOnlyField(source="lecture_session.timetable_entry.course.title")
    timetable_entry_title = serializers.ReadOnlyField(source="lecture_session.timetable_entry.title")
    session_date = serializers.ReadOnlyField(source="lecture_session.session_date")
    session_start_time = serializers.SerializerMethodField()
    session_end_time = serializers.SerializerMethodField()
    venue_id = serializers.SerializerMethodField()
    venue_name = serializers.SerializerMethodField()
    lecturer_name = serializers.SerializerMethodField()
    lecturers = serializers.SerializerMethodField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = ClassRepReport
        fields = (
            "id",
            "lecture_session",
            "timetable_entry_title",
            "course_code",
            "course_title",
            "session_date",
            "session_start_time",
            "session_end_time",
            "venue_id",
            "venue_name",
            "lecturer_name",
            "lecturers",
            "reported_by",
            "reported_by_name",
            "held",
            "reason",
            "reported_at",
            "window_expires_at",
            "lecturer_response",
            "lecturer_responded_at",
        )
        read_only_fields = (
            "id",
            "reported_by",
            "reported_at",
            "window_expires_at",
            "lecturer_response",
            "lecturer_responded_at",
            "timetable_entry_title",
            "course_code",
            "course_title",
            "session_date",
            "session_start_time",
            "session_end_time",
            "venue_id",
            "venue_name",
            "lecturer_name",
            "lecturers",
            "reported_by_name",
        )

    def get_session_start_time(self, obj):
        session = getattr(obj, "lecture_session", None)
        if session and session.session_start_time:
            return str(session.session_start_time)[:5]
        entry = getattr(session, "timetable_entry", None)
        if entry and entry.start_time:
            return str(entry.start_time)[:5]
        return "09:00"

    def get_session_end_time(self, obj):
        session = getattr(obj, "lecture_session", None)
        if session and session.session_end_time:
            return str(session.session_end_time)[:5]
        entry = getattr(session, "timetable_entry", None)
        if entry and entry.end_time:
            return str(entry.end_time)[:5]
        return "11:00"

    def get_venue_id(self, obj):
        session = getattr(obj, "lecture_session", None)
        if session and session.venue_id:
            return str(session.venue_id)
        entry = getattr(session, "timetable_entry", None)
        if entry and entry.venue_id:
            return str(entry.venue_id)
        return None

    def get_venue_name(self, obj):
        session = getattr(obj, "lecture_session", None)
        if session and getattr(session, "venue", None):
            return session.venue.name
        entry = getattr(session, "timetable_entry", None)
        if entry and getattr(entry, "venue", None):
            return entry.venue.name
        return "TBA"

    def get_lecturer_name(self, obj):
        session = getattr(obj, "lecture_session", None)
        course = getattr(getattr(session, "timetable_entry", None), "course", None)
        if not course:
            return ""
        first_lec = course.lecturers.first()
        return first_lec.full_name if first_lec else ""

    def get_lecturers(self, obj):
        session = getattr(obj, "lecture_session", None)
        course = getattr(getattr(session, "timetable_entry", None), "course", None)
        if not course:
            return []
        return [
            {
                "id": str(l.id),
                "name": l.full_name,
                "full_name": l.full_name,
                "staff_id": getattr(l, "staff_id", ""),
                "email": getattr(l, "email", "") or "",
            }
            for l in course.lecturers.all()
        ]

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        report = create_class_rep_report(
            student_user=user,
            session=validated_data.get("lecture_session"),
            held=validated_data.get("held"),
            reason=validated_data.get("reason"),
        )
        return report


class LecturerResponseSerializer(serializers.Serializer):
    response_text = serializers.CharField(required=True)


class UnreportedSessionFlagSerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="lecture_session.timetable_entry.course.code")
    timetable_entry_title = serializers.ReadOnlyField(source="lecture_session.timetable_entry.title")
    session_date = serializers.ReadOnlyField(source="lecture_session.session_date")
    acknowledged_by_name = serializers.ReadOnlyField(source="acknowledged_by.full_name")

    class Meta:
        model = UnreportedSessionFlag
        fields = (
            "id",
            "lecture_session",
            "timetable_entry_title",
            "course_code",
            "session_date",
            "flagged_at",
            "acknowledged_by",
            "acknowledged_by_name",
            "acknowledged_at",
        )
        read_only_fields = fields


class AnalyticsQueryParamsSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    department_id = serializers.IntegerField(required=False)
    faculty_id = serializers.IntegerField(required=False)
    course_id = serializers.IntegerField(required=False)
    level = serializers.IntegerField(required=False)
    program_id = serializers.IntegerField(required=False)
    lecturer_id = serializers.IntegerField(required=False)
    semester_id = serializers.IntegerField(required=False)
    venue_id = serializers.IntegerField(required=False)
    request_type = serializers.CharField(required=False)
    group_by = serializers.CharField(required=False, default="course")

