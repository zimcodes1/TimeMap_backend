from rest_framework import serializers

from .models import ClassRepReport, UnreportedSessionFlag
from .services import create_class_rep_report


class ClassRepReportSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.ReadOnlyField(source="reported_by.full_name")
    course_code = serializers.ReadOnlyField(source="lecture_session.timetable_entry.course.code")
    course_title = serializers.ReadOnlyField(source="lecture_session.timetable_entry.course.title")
    timetable_entry_title = serializers.ReadOnlyField(source="lecture_session.timetable_entry.title")
    session_date = serializers.ReadOnlyField(source="lecture_session.session_date")

    class Meta:
        model = ClassRepReport
        fields = (
            "id",
            "lecture_session",
            "timetable_entry_title",
            "course_code",
            "course_title",
            "session_date",
            "reported_by",
            "reported_by_name",
            "held",
            "reason",
            "reported_at",
            "window_expires_at",
            "lecturer_response",
            "lecturer_responded_at",
        )
        read_only_fields = ("id", "reported_by", "reported_at", "window_expires_at", "lecturer_response", "lecturer_responded_at")

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
    course_id = serializers.IntegerField(required=False)
    venue_id = serializers.IntegerField(required=False)
    request_type = serializers.CharField(required=False)
    group_by = serializers.CharField(required=False, default="course")

