from courses.models import CourseRegistration
from rest_framework import serializers

from .models import ExamSitting, LectureSession, TimetableEntry
from .services import materialize_timetable_entry


class TimetableEntrySerializer(serializers.ModelSerializer):
    course_code = serializers.ReadOnlyField(source="course.code")
    venue_name = serializers.ReadOnlyField(source="venue.name")
    created_by_name = serializers.ReadOnlyField(source="created_by.full_name")

    class Meta:
        model = TimetableEntry
        fields = (
            "id",
            "entry_type",
            "title",
            "course",
            "course_code",
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
            "academic_session",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_at")

    def create(self, validated_data):
        entry = super().create(validated_data)

        # Trigger materialization automatically if it's a recurring lecture
        if entry.entry_type == TimetableEntry.EntryType.LECTURE and entry.recurrence_rule:
            materialize_timetable_entry(entry)

        return entry


class LectureSessionSerializer(serializers.ModelSerializer):
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    course_code = serializers.ReadOnlyField(source="timetable_entry.course.code")
    venue_name = serializers.ReadOnlyField(source="venue.name")

    class Meta:
        model = LectureSession
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "course_code",
            "session_date",
            "session_start_time",
            "session_end_time",
            "venue",
            "venue_name",
            "status",
        )
        read_only_fields = ("id",)


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
