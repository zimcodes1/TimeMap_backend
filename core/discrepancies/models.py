from accounts.models import AdminOfficer, User
from django.db import models
from scheduling.models import TimetableEntry
from venues.models import Venue


class DiscrepancyRequest(models.Model):
    class RequestType(models.TextChoices):
        SHIFT_VENUE = "shift_venue", "Shift Venue"
        SHIFT_TIME = "shift_time", "Shift Time"
        POSTPONE = "postpone", "Postpone"
        CANCEL = "cancel", "Cancel"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    timetable_entry = models.ForeignKey(TimetableEntry, on_delete=models.CASCADE, related_name="discrepancy_requests")
    request_type = models.CharField(max_length=30, choices=RequestType.choices)
    proposed_venue = models.ForeignKey(
        Venue, null=True, blank=True, on_delete=models.SET_NULL, related_name="proposed_discrepancies"
    )
    proposed_start_time = models.TimeField(null=True, blank=True)
    proposed_date = models.DateField(null=True, blank=True)
    reason = models.TextField()

    initiated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="initiated_discrepancies")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    routed_to = models.ForeignKey(
        AdminOfficer, null=True, blank=True, on_delete=models.SET_NULL, related_name="routed_discrepancies"
    )
    decided_by = models.ForeignKey(
        AdminOfficer, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_discrepancies"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DiscrepancyRequest #{self.id} - {self.request_type} ({self.status})"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.CharField(max_length=20, choices=Action.choices)
    target_model = models.CharField(max_length=100)
    target_id = models.IntegerField()
    before_snapshot = models.JSONField(null=True, blank=True)
    after_snapshot = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AuditLog {self.action} on {self.target_model}:{self.target_id} by {self.actor.identifier}"
