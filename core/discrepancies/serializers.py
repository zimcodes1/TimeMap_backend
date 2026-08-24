from rest_framework import serializers

from .models import AuditLog, DiscrepancyRequest
from .services import process_discrepancy_submission


class DiscrepancyRequestSerializer(serializers.ModelSerializer):
    initiated_by_name = serializers.SerializerMethodField()
    initiated_by_scope = serializers.SerializerMethodField()
    proposed_venue_name = serializers.ReadOnlyField(source="proposed_venue.name")
    decided_by_name = serializers.ReadOnlyField(source="decided_by.full_name")
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    course_code = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    lecture_session_info = serializers.SerializerMethodField()

    class Meta:
        model = DiscrepancyRequest
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "lecture_session",
            "lecture_session_info",
            "course_code",
            "course_title",
            "request_type",
            "proposed_venue",
            "proposed_venue_name",
            "proposed_start_time",
            "proposed_end_time",
            "proposed_date",
            "reason",
            "initiated_by",
            "initiated_by_name",
            "initiated_by_scope",
            "status",
            "routed_to",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "created_at",
        )
        read_only_fields = ("id", "initiated_by", "status", "routed_to", "decided_by", "decided_at", "created_at")

    def get_initiated_by_name(self, obj):
        if not obj.initiated_by:
            return "System Admin"
        user = obj.initiated_by
        if hasattr(user, "admin_profile") and user.admin_profile and user.admin_profile.full_name:
            return user.admin_profile.full_name
        if hasattr(user, "lecturer_profile") and user.lecturer_profile and user.lecturer_profile.full_name:
            return user.lecturer_profile.full_name
        if hasattr(user, "student_profile") and user.student_profile and user.student_profile.full_name:
            return user.student_profile.full_name
        return user.identifier

    def get_initiated_by_scope(self, obj):
        if not obj.initiated_by:
            return "CYB"
        user = obj.initiated_by
        if hasattr(user, "admin_profile") and user.admin_profile:
            prof = user.admin_profile
            if prof.scope_department:
                return prof.scope_department.code
            if prof.scope_faculty:
                return prof.scope_faculty.code
            if prof.scope_school:
                return prof.scope_school.code
            return prof.level.upper()
        if hasattr(user, "lecturer_profile") and user.lecturer_profile and user.lecturer_profile.department:
            return user.lecturer_profile.department.code
        if hasattr(user, "student_profile") and user.student_profile and user.student_profile.department:
            return user.student_profile.department.code
        return "CYB"

    def get_course_code(self, obj):
        if obj.timetable_entry and obj.timetable_entry.course:
            return obj.timetable_entry.course.code
        if obj.lecture_session and obj.lecture_session.timetable_entry and obj.lecture_session.timetable_entry.course:
            return obj.lecture_session.timetable_entry.course.code
        if obj.timetable_entry and obj.timetable_entry.title:
            parts = obj.timetable_entry.title.split("—")
            return parts[0].strip()
        return "CYB-212"

    def get_course_title(self, obj):
        if obj.timetable_entry and obj.timetable_entry.course:
            return obj.timetable_entry.course.title
        if obj.lecture_session and obj.lecture_session.timetable_entry and obj.lecture_session.timetable_entry.course:
            return obj.lecture_session.timetable_entry.course.title
        if obj.timetable_entry and obj.timetable_entry.title:
            parts = obj.timetable_entry.title.split("—")
            return parts[1].strip() if len(parts) > 1 else parts[0].strip()
        return "Cybersecurity & Cryptography"

    def get_lecture_session_info(self, obj):
        if obj.lecture_session:
            return f"Session #{obj.lecture_session.id} on {obj.lecture_session.session_date}"
        return None

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        discrepancy = process_discrepancy_submission(
            user=user,
            request_type=validated_data.get("request_type"),
            timetable_entry=validated_data.get("timetable_entry"),
            lecture_session=validated_data.get("lecture_session"),
            proposed_venue=validated_data.get("proposed_venue"),
            proposed_start_time=validated_data.get("proposed_start_time"),
            proposed_end_time=validated_data.get("proposed_end_time"),
            proposed_date=validated_data.get("proposed_date"),
            reason=validated_data.get("reason", ""),
        )
        return discrepancy


class AuditLogSerializer(serializers.ModelSerializer):
    actor_identifier = serializers.ReadOnlyField(source="actor.identifier")

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "actor_identifier",
            "action",
            "target_model",
            "target_id",
            "before_snapshot",
            "after_snapshot",
            "timestamp",
        )
        read_only_fields = fields
