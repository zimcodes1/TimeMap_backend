import datetime
from accounts.models import AdminOfficer
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from scheduling.conflict_engine import check_venue_overlap, determine_booking_routing
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
    Ensures that only admin officers can apply, validates internal consistency per request_type,
    operating hours (8am-6pm), and instance vs pattern level targeting.
    """
    if not user or not user.is_authenticated or user.role != "admin" or not hasattr(user, "admin_profile") or not user.admin_profile:
        raise serializers.ValidationError({"detail": "Only admin officers are authorized to submit discrepancy requests."})

    if request_type != DiscrepancyRequest.RequestType.CREATE_BOOKING:
        if not timetable_entry:
            raise serializers.ValidationError({"detail": "Discrepancy requests can only be submitted for recurring timetable schedule patterns."})
        if lecture_session:
            raise serializers.ValidationError({"detail": "Discrepancy requests cannot target individual dated sessions. Shifting dated session instances is performed directly."})

    if request_type == DiscrepancyRequest.RequestType.SHIFT_VENUE:
        if not proposed_venue:
            raise serializers.ValidationError({"proposed_venue": "Proposed venue is required for a shift_venue request."})
    elif request_type == DiscrepancyRequest.RequestType.SHIFT_TIME:
        if not proposed_start_time and not proposed_date:
            raise serializers.ValidationError({"detail": "Either proposed_start_time or proposed_date must be specified for a shift_time request."})
    elif request_type in [DiscrepancyRequest.RequestType.CANCEL, DiscrepancyRequest.RequestType.POSTPONE]:
        if not reason:
            raise serializers.ValidationError({"reason": "Reason is required when cancelling or postponing."})

    # Enforce standard operating hours: 8:00 AM to 6:00 PM (08:00 to 18:00)
    day_start = datetime.time(8, 0, 0)
    day_end = datetime.time(18, 0, 0)

    if proposed_start_time and (proposed_start_time < day_start or proposed_start_time >= day_end):
        raise serializers.ValidationError({"proposed_start_time": "Proposed start time must be within standard operating hours (8:00 AM - 6:00 PM)."})
    if proposed_end_time and (proposed_end_time <= day_start or proposed_end_time > day_end):
        raise serializers.ValidationError({"proposed_end_time": "Proposed end time must be within standard operating hours (8:00 AM - 6:00 PM)."})
    if proposed_start_time and proposed_end_time and proposed_start_time >= proposed_end_time:
        raise serializers.ValidationError({"detail": "Proposed start time must be before proposed end time."})


def resolve_discrepancy_routing_admin(venue):
    """
    Resolves the AdminOfficer responsible for the given venue based on its owning hierarchy:
    - Department level: routed to the Department Admin Officer.
    - Faculty level: routed to the Faculty Admin Officer.
    - School level: routed to the School Admin Officer.
    Fallback to upper administrative level if the specific tier admin is unassigned.
    """
    if not venue:
        return None

    if venue.owning_level == Venue.OwningLevel.DEPARTMENT and venue.owning_department:
        dept_admin = AdminOfficer.objects.filter(
            level=AdminOfficer.Level.DEPARTMENT,
            scope_department=venue.owning_department,
        ).first()
        if dept_admin:
            return dept_admin
        if venue.owning_department.faculty:
            fac_admin = AdminOfficer.objects.filter(
                level=AdminOfficer.Level.FACULTY,
                scope_faculty=venue.owning_department.faculty,
            ).first()
            if fac_admin:
                return fac_admin
            if venue.owning_department.faculty.school:
                return AdminOfficer.objects.filter(
                    level=AdminOfficer.Level.SCHOOL,
                    scope_school=venue.owning_department.faculty.school,
                ).first()

    elif venue.owning_level == Venue.OwningLevel.FACULTY and venue.owning_faculty:
        fac_admin = AdminOfficer.objects.filter(
            level=AdminOfficer.Level.FACULTY,
            scope_faculty=venue.owning_faculty,
        ).first()
        if fac_admin:
            return fac_admin
        if venue.owning_faculty.school:
            return AdminOfficer.objects.filter(
                level=AdminOfficer.Level.SCHOOL,
                scope_school=venue.owning_faculty.school,
            ).first()

    elif venue.owning_level == Venue.OwningLevel.SCHOOL and venue.owning_school:
        return AdminOfficer.objects.filter(
            level=AdminOfficer.Level.SCHOOL,
            scope_school=venue.owning_school,
        ).first()

    if venue.owning_faculty:
        fac_admin = AdminOfficer.objects.filter(
            level=AdminOfficer.Level.FACULTY,
            scope_faculty=venue.owning_faculty,
        ).first()
        if fac_admin:
            return fac_admin

    return None


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
    Validates payload, cross-checks that the proposed venue-time is available (no schedule clashes),
    determines the responsible routing admin based on venue ownership hierarchy, and creates DiscrepancyRequest.
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

    # Determine target room, date, and times for availability and routing
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

    # For changes in venue, time, or new bookings: cross-check that proposed venue-time is available
    if request_type in [
        DiscrepancyRequest.RequestType.SHIFT_VENUE,
        DiscrepancyRequest.RequestType.SHIFT_TIME,
        DiscrepancyRequest.RequestType.CREATE_BOOKING,
    ]:
        if target_venue and target_date and target_start and target_end:
            r_rule = timetable_entry.recurrence_rule if timetable_entry else None
            r_start = timetable_entry.recurrence_start_date if timetable_entry else None
            r_end = timetable_entry.recurrence_end_date if timetable_entry else None
            conflicts = check_venue_overlap(
                venue=target_venue,
                date=target_date,
                start_time=target_start,
                end_time=target_end,
                recurrence_rule=r_rule,
                recurrence_start_date=r_start,
                recurrence_end_date=r_end,
                exclude_entry_id=exclude_entry_id,
                exclude_session_id=exclude_session_id,
            )
            if conflicts:
                raise serializers.ValidationError({
                    "detail": "Proposed change creates a schedule conflict. The proposed venue is not available at the requested time.",
                    "conflicts": conflicts,
                })

    # Route request to the admin officer on to whose department/scope the venue belongs
    routed_admin = resolve_discrepancy_routing_admin(target_venue)
    routed_to_id = routed_admin.id if routed_admin else None

    # If venue is unassigned to any admin profile, fallback to the user's admin profile if admin
    if not routed_to_id and hasattr(user, "admin_profile") and user.admin_profile:
        routed_to_id = user.admin_profile.id

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

    # Dispatch notification to routed admin officer
    if routed_to_id:
        try:
            routed_admin = AdminOfficer.objects.filter(id=routed_to_id).first()
            if routed_admin and routed_admin.user:
                from notifications.models import Notification
                from notifications.services import dispatch_event_notification
                dispatch_event_notification(
                    recipient=routed_admin.user,
                    notification_type=Notification.NotificationType.DISCREPANCY_SUBMITTED,
                    title="New Discrepancy Request Pending Approval",
                    body=f"A new {request_type} discrepancy request #{discrepancy.id} has been routed to you for approval.",
                    related_model="DiscrepancyRequest",
                    related_id=discrepancy.id,
                )
        except Exception:
            pass

    return discrepancy


def apply_discrepancy_request(discrepancy):
    """
    Applies an approved discrepancy request to the underlying live schedule records.
    Transitions status from APPROVED to APPLIED.
    Frees up previous venue-time immediately by updating or cancelling live session records.
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
        sessions_to_update = LectureSession.objects.filter(timetable_entry=entry)

        if req_type == DiscrepancyRequest.RequestType.SHIFT_VENUE and discrepancy.proposed_venue:
            entry.venue = discrepancy.proposed_venue
            sessions_to_update.update(venue=discrepancy.proposed_venue)
        elif req_type == DiscrepancyRequest.RequestType.SHIFT_TIME:
            update_fields = {}
            if discrepancy.proposed_start_time:
                entry.start_time = discrepancy.proposed_start_time
                update_fields["session_start_time"] = discrepancy.proposed_start_time
            if discrepancy.proposed_end_time:
                entry.end_time = discrepancy.proposed_end_time
                update_fields["session_end_time"] = discrepancy.proposed_end_time
            if discrepancy.proposed_date:
                entry.recurrence_start_date = discrepancy.proposed_date
            if update_fields:
                sessions_to_update.update(**update_fields)

        if req_type == DiscrepancyRequest.RequestType.CANCEL:
            entry.status = TimetableEntry.Status.CANCELLED
            sessions_to_update.update(status=LectureSession.Status.CANCELLED)
        elif req_type == DiscrepancyRequest.RequestType.POSTPONE:
            entry.status = TimetableEntry.Status.POSTPONED
            sessions_to_update.update(status=LectureSession.Status.POSTPONED)

        entry.save()
        if entry.entry_type == TimetableEntry.EntryType.LECTURE and entry.recurrence_rule:
            materialize_timetable_entry(entry)

    discrepancy.status = DiscrepancyRequest.Status.APPROVED
    discrepancy.save()


def approve_discrepancy_request(discrepancy, admin_user):
    """
    Approves a pending discrepancy request after verifying conflict safety and routing authority.
    Only the admin officer to whom the request is routed can approve it.
    """
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot approve request with status '{discrepancy.status}'."})

    if (
        not admin_user
        or not admin_user.is_authenticated
        or admin_user.role != "admin"
        or not hasattr(admin_user, "admin_profile")
        or not admin_user.admin_profile
    ):
        raise PermissionDenied("Only admin officers can approve discrepancy requests.")

    admin_prof = admin_user.admin_profile

    if discrepancy.routed_to_id != admin_prof.id:
        raise PermissionDenied("Only the admin officer to whom the request is routed can approve it.")

    # Re-evaluate venue conflict check right at approval time
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
        conflicts = check_venue_overlap(
            venue=target_venue,
            date=target_date,
            start_time=target_start,
            end_time=target_end,
            exclude_entry_id=exclude_entry_id,
            exclude_session_id=exclude_session_id,
        )
        if conflicts:
            raise serializers.ValidationError({
                "detail": "Cannot approve: proposed change creates a new schedule conflict with an existing session.",
                "conflicts": conflicts,
            })

    discrepancy.status = DiscrepancyRequest.Status.APPROVED
    discrepancy.decided_by = admin_prof
    discrepancy.decided_at = timezone.now()
    discrepancy.save()

    # Automatically trigger database application
    apply_discrepancy_request(discrepancy)

    # Notify requester
    if discrepancy.initiated_by:
        try:
            from notifications.models import Notification
            from notifications.services import dispatch_event_notification
            dispatch_event_notification(
                recipient=discrepancy.initiated_by,
                notification_type=Notification.NotificationType.DISCREPANCY_APPROVED,
                title="Discrepancy Request Approved",
                body=f"Your {discrepancy.request_type} request #{discrepancy.id} has been approved and applied.",
                related_model="DiscrepancyRequest",
                related_id=discrepancy.id,
            )
        except Exception:
            pass

    return discrepancy


def reject_discrepancy_request(discrepancy, admin_user, reason=""):
    """
    Rejects a pending discrepancy request.
    Only the admin officer to whom the request is routed can reject it.
    """
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot reject request with status '{discrepancy.status}'."})

    if (
        not admin_user
        or not admin_user.is_authenticated
        or admin_user.role != "admin"
        or not hasattr(admin_user, "admin_profile")
        or not admin_user.admin_profile
    ):
        raise PermissionDenied("Only admin officers can reject discrepancy requests.")

    admin_prof = admin_user.admin_profile

    if discrepancy.routed_to_id != admin_prof.id:
        raise PermissionDenied("Only the admin officer to whom the request is routed can reject it.")

    discrepancy.status = DiscrepancyRequest.Status.REJECTED
    discrepancy.decided_by = admin_prof
    discrepancy.decided_at = timezone.now()
    discrepancy.save()

    # Notify requester
    if discrepancy.initiated_by:
        try:
            from notifications.models import Notification
            from notifications.services import dispatch_event_notification
            dispatch_event_notification(
                recipient=discrepancy.initiated_by,
                notification_type=Notification.NotificationType.DISCREPANCY_REJECTED,
                title="Discrepancy Request Rejected",
                body=f"Your {discrepancy.request_type} request #{discrepancy.id} was rejected. {reason}",
                related_model="DiscrepancyRequest",
                related_id=discrepancy.id,
            )
        except Exception:
            pass

    return discrepancy


def withdraw_discrepancy_request(discrepancy, user):
    """
    Withdraws a pending discrepancy request by the original requester.
    """
    if discrepancy.initiated_by != user:
        raise PermissionDenied("Only the original requesting admin can withdraw this request.")
    if discrepancy.status != DiscrepancyRequest.Status.PENDING:
        raise serializers.ValidationError({"detail": f"Cannot withdraw request with status '{discrepancy.status}'."})

    discrepancy.status = DiscrepancyRequest.Status.WITHDRAWN
    discrepancy.save()
    return discrepancy

