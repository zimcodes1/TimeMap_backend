import datetime
from accounts.models import AdminOfficer
from django.utils import timezone
from rest_framework import serializers
from scheduling.conflict_engine import determine_booking_routing
from scheduling.models import LectureSession, TimetableEntry
from scheduling.services import materialize_timetable_entry
from venues.models import Venue

from .models import DiscrepancyRequest


def validate_discrepancy_submission(
    user,
    request_type,
    timetable_entry=None,
    lecture_session=None,
    proposed_venue=None,
    proposed_start_time=None,
    proposed_end_time=None,
    proposed_date=None,
    reason=None,
):
    """
    Ensures internal consistency per request_type and validates instance-level vs pattern-level targeting.
    """
    if request_type != DiscrepancyRequest.RequestType.CREATE_BOOKING:
        if not timetable_entry and not lecture_session:
            raise serializers.ValidationError({"detail": "Discrepancy request must target either a timetable_entry (pattern) or a lecture_session (instance)."})
        if timetable_entry and lecture_session:
            raise serializers.ValidationError({"detail": "Cannot target both a timetable_entry and a lecture_session in a single request."})

    if request_type == DiscrepancyRequest.RequestType.SHIFT_VENUE:
        if not proposed_venue:
            raise serializers.ValidationError({"proposed_venue": "Proposed venue is required for a shift_venue request."})
    elif request_type == DiscrepancyRequest.RequestType.SHIFT_TIME:
        if not proposed_start_time and not proposed_date:
            raise serializers.ValidationError({"detail": "Either proposed_start_time or proposed_date must be specified for a shift_time request."})
    elif request_type in [DiscrepancyRequest.RequestType.CANCEL, DiscrepancyRequest.RequestType.POSTPONE]:
        if not reason:
            raise serializers.ValidationError({"reason": "Reason is required when cancelling or postponing."})


def process_discrepancy_submission(
    user,
    request_type,
    timetable_entry=None,
    lecture_session=None,
    proposed_venue=None,
    proposed_start_time=None,
    proposed_end_time=None,
    proposed_date=None,
    reason="",
):
    """
    Validates payload, re-runs Conflict Detection Engine against the proposed change, and creates DiscrepancyRequest.
    """
    validate_discrepancy_submission(
        user=user,
        request_type=request_type,
        timetable_entry=timetable_entry,
        lecture_session=lecture_session,
        proposed_venue=proposed_venue,
        proposed_start_time=proposed_start_time,
        proposed_end_time=proposed_end_time,
        proposed_date=proposed_date,
        reason=reason,
    )

    # Determine target room, date, and times for conflict check
    target_venue = proposed_venue
    target_date = proposed_date
    target_start = proposed_start_time
    target_end = proposed_end_time

    exclude_entry_id = None
    exclude_session_id = None

    if lecture_session:
        target_venue = target_venue or lecture_session.venue
        target_date = target_date or lecture_session.session_date
        target_start = target_start or lecture_session.session_start_time
        target_end = target_end or lecture_session.session_end_time
        exclude_session_id = lecture_session.id
        exclude_entry_id = lecture_session.timetable_entry_id
    elif timetable_entry:
        target_venue = target_venue or timetable_entry.venue
        target_date = target_date or timetable_entry.recurrence_start_date
        target_start = target_start or timetable_entry.start_time
        target_end = target_end or timetable_entry.end_time
        exclude_entry_id = timetable_entry.id

    if target_venue and target_date and target_start and target_end:
        routing = determine_booking_routing(
            user=user,
            venue=target_venue,
            date_or_start_date=target_date,
            start_time=target_start,
            end_time=target_end,
            exclude_entry_id=exclude_entry_id,
        )

        if routing["outcome"] == "HARD_REJECT":
            raise serializers.ValidationError({
                "detail": "Proposed change creates a new schedule conflict.",
                "conflicts": routing["conflicts"],
            })

        routed_to_id = routing.get("routed_to_admin_id")
    else:
        routed_to_id = None

    discrepancy = DiscrepancyRequest.objects.create(
        timetable_entry=timetable_entry,
        lecture_session=lecture_session,
        request_type=request_type,
        proposed_venue=proposed_venue,
        proposed_start_time=proposed_start_time,
        proposed_end_time=proposed_end_time,
        proposed_date=proposed_date,
        reason=reason,
        initiated_by=user,
        status=DiscrepancyRequest.Status.PENDING,
        routed_to_id=routed_to_id,
    )

    return discrepancy


def apply_discrepancy_request(discrepancy):
    """
    Applies an approved discrepancy request to the underlying live schedule records.
    Transitions status from APPROVED to APPLIED.
    """
    if discrepancy.status != DiscrepancyRequest.Status.APPROVED:
        return

    req_type = discrepancy.request_type

    # Instance-Level Application (LectureSession)
    if discrepancy.lecture_session:
        session = discrepancy.lecture_session
        if req_type == DiscrepancyRequest.RequestType.SHIFT_VENUE and discrepancy.proposed_venue:
            session.venue = discrepancy.proposed_venue
            session.status = LectureSession.Status.SHIFTED
        elif req_type == DiscrepancyRequest.RequestType.SHIFT_TIME:
            if discrepancy.proposed_start_time:
                session.session_start_time = discrepancy.proposed_start_time
            if discrepancy.proposed_end_time:
                session.session_end_time = discrepancy.proposed_end_time
            if discrepancy.proposed_date:
                session.session_date = discrepancy.proposed_date
            session.status = LectureSession.Status.SHIFTED
        elif req_type == DiscrepancyRequest.RequestType.POSTPONE:
            session.status = LectureSession.Status.POSTPONED
        elif req_type == DiscrepancyRequest.RequestType.CANCEL:
            session.status = LectureSession.Status.CANCELLED

        session.save()

    # Pattern-Level Application (TimetableEntry)
    elif discrepancy.timetable_entry:
        entry = discrepancy.timetable_entry
        if req_type == DiscrepancyRequest.RequestType.SHIFT_VENUE and discrepancy.proposed_venue:
            entry.venue = discrepancy.proposed_venue
        elif req_type == DiscrepancyRequest.RequestType.SHIFT_TIME:
            if discrepancy.proposed_start_time:
                entry.start_time = discrepancy.proposed_start_time
            if discrepancy.proposed_end_time:
                entry.end_time = discrepancy.proposed_end_time
            if discrepancy.proposed_date:
                entry.recurrence_start_date = discrepancy.proposed_date

        if req_type == DiscrepancyRequest.RequestType.CANCEL:
            entry.status = TimetableEntry.Status.CANCELLED
        elif req_type == DiscrepancyRequest.RequestType.POSTPONE:
            entry.status = TimetableEntry.Status.POSTPONED

        entry.save()
        if entry.entry_type == TimetableEntry.EntryType.LECTURE and entry.recurrence_rule:
            materialize_timetable_entry(entry)

    discrepancy.status = DiscrepancyRequest.Status.APPLIED
    discrepancy.save()


def approve_discrepancy_request(discrepancy, admin_user):
    """
    Approves a pending discrepancy request after verifying conflict safety.
    """
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot approve request with status '{discrepancy.status}'."})

    # Re-evaluate Conflict Engine right at approval time
    target_venue = discrepancy.proposed_venue
    target_date = discrepancy.proposed_date
    target_start = discrepancy.proposed_start_time
    target_end = discrepancy.proposed_end_time

    exclude_entry_id = None
    exclude_session_id = None

    if discrepancy.lecture_session:
        target_venue = target_venue or discrepancy.lecture_session.venue
        target_date = target_date or discrepancy.lecture_session.session_date
        target_start = target_start or discrepancy.lecture_session.session_start_time
        target_end = target_end or discrepancy.lecture_session.session_end_time
        exclude_session_id = discrepancy.lecture_session.id
        exclude_entry_id = discrepancy.lecture_session.timetable_entry_id
    elif discrepancy.timetable_entry:
        target_venue = target_venue or discrepancy.timetable_entry.venue
        target_date = target_date or discrepancy.timetable_entry.recurrence_start_date
        target_start = target_start or discrepancy.timetable_entry.start_time
        target_end = target_end or discrepancy.timetable_entry.end_time
        exclude_entry_id = discrepancy.timetable_entry.id

    if target_venue and target_date and target_start and target_end:
        routing = determine_booking_routing(
            user=admin_user,
            venue=target_venue,
            date_or_start_date=target_date,
            start_time=target_start,
            end_time=target_end,
            exclude_entry_id=exclude_entry_id,
        )

        if routing["outcome"] == "HARD_REJECT":
            raise serializers.ValidationError({
                "detail": "Cannot approve: proposed change creates a new schedule conflict.",
                "conflicts": routing["conflicts"],
            })

    admin_prof = admin_user.admin_profile if hasattr(admin_user, "admin_profile") else None

    discrepancy.status = DiscrepancyRequest.Status.APPROVED
    discrepancy.decided_by = admin_prof
    discrepancy.decided_at = timezone.now()
    discrepancy.save()

    # Automatically trigger database application
    apply_discrepancy_request(discrepancy)
    return discrepancy


def reject_discrepancy_request(discrepancy, admin_user, reason=""):
    """
    Rejects a pending discrepancy request.
    """
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot reject request with status '{discrepancy.status}'."})

    admin_prof = admin_user.admin_profile if hasattr(admin_user, "admin_profile") else None

    discrepancy.status = DiscrepancyRequest.Status.REJECTED
    discrepancy.decided_by = admin_prof
    discrepancy.decided_at = timezone.now()
    discrepancy.save()
    return discrepancy


def withdraw_discrepancy_request(discrepancy, user):
    """
    Withdraws a pending discrepancy request by the original requester.
    """
    if discrepancy.initiated_by != user:
        raise serializers.ValidationError({"detail": "Only the original requester can withdraw this request."})
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot withdraw request with status '{discrepancy.status}'."})

    discrepancy.status = DiscrepancyRequest.Status.WITHDRAWN
    discrepancy.save()
    return discrepancy
