from rest_framework import serializers

from .models import AuditLog, DiscrepancyRequest
from .services import process_discrepancy_submission


class DiscrepancyRequestSerializer(serializers.ModelSerializer):
    initiated_by_name = serializers.ReadOnlyField(source="initiated_by.identifier")
    proposed_venue_name = serializers.ReadOnlyField(source="proposed_venue.name")
    decided_by_name = serializers.ReadOnlyField(source="decided_by.full_name")
    timetable_entry_title = serializers.ReadOnlyField(source="timetable_entry.title")
    lecture_session_info = serializers.SerializerMethodField()

    class Meta:
        model = DiscrepancyRequest
        fields = (
            "id",
            "timetable_entry",
            "timetable_entry_title",
            "lecture_session",
            "lecture_session_info",
            "request_type",
            "proposed_venue",
            "proposed_venue_name",
            "proposed_start_time",
            "proposed_end_time",
            "proposed_date",
            "reason",
            "initiated_by",
            "initiated_by_name",
            "status",
            "routed_to",
            "decided_by",
            "decided_by_name",
            "decided_at",
            "created_at",
        )
        read_only_fields = ("id", "initiated_by", "status", "routed_to", "decided_by", "decided_at", "created_at")

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
