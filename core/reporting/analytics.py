import datetime
from accounts.permissions import (
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from courses.models import Course
from discrepancies.models import DiscrepancyRequest
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from scheduling.models import LectureSession
from venues.models import Venue

from .models import ClassRepReport


def get_lecture_hold_rate_analytics(
    user, start_date=None, end_date=None, department_id=None, course_id=None, group_by="course"
):
    """
    Computes lecture-hold rate analytics (total reports, held count, not held count, percentage)
    scoped to user authority level and grouped by course, lecturer, or department.
    """
    dept_qs = get_user_scope_departments(user)
    reports = ClassRepReport.objects.filter(
        lecture_session__timetable_entry__course__owning_department__in=dept_qs
    )

    if start_date:
        reports = reports.filter(lecture_session__session_date__gte=start_date)
    if end_date:
        reports = reports.filter(lecture_session__session_date__lte=end_date)
    if department_id:
        reports = reports.filter(lecture_session__timetable_entry__course__owning_department_id=department_id)
    if course_id:
        reports = reports.filter(lecture_session__timetable_entry__course_id=course_id)

    total_reports = reports.count()
    held_count = reports.filter(held=True).count()
    not_held_count = reports.filter(held=False).count()
    hold_rate_percentage = round((held_count / total_reports) * 100, 2) if total_reports > 0 else 0.0

    breakdown = []
    if group_by == "course":
        course_map = {}
        for r in reports.values(
            "lecture_session__timetable_entry__course_id",
            "lecture_session__timetable_entry__course__code",
            "lecture_session__timetable_entry__course__title",
            "held",
        ):
            cid = r["lecture_session__timetable_entry__course_id"]
            if cid not in course_map:
                course_map[cid] = {
                    "course_id": cid,
                    "course_code": r["lecture_session__timetable_entry__course__code"],
                    "course_title": r["lecture_session__timetable_entry__course__title"],
                    "total_reports": 0,
                    "held_count": 0,
                    "not_held_count": 0,
                }
            course_map[cid]["total_reports"] += 1
            if r["held"]:
                course_map[cid]["held_count"] += 1
            else:
                course_map[cid]["not_held_count"] += 1

        for c in course_map.values():
            tot = c["total_reports"]
            h = c["held_count"]
            c["hold_rate_percentage"] = round((h / tot) * 100, 2) if tot > 0 else 0.0
            breakdown.append(c)

    return {
        "summary": {
            "total_reports": total_reports,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "hold_rate_percentage": hold_rate_percentage,
        },
        "breakdown": breakdown,
    }


def get_venue_utilization_analytics(user, start_date=None, end_date=None, venue_id=None, group_by="venue"):
    """
    Computes venue utilization hours for lectures across venues in user scope.
    """
    dept_qs = get_user_scope_departments(user)
    sessions = LectureSession.objects.filter(venue__owning_department__in=dept_qs).exclude(
        status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED]
    )

    if start_date:
        sessions = sessions.filter(session_date__gte=start_date)
    if end_date:
        sessions = sessions.filter(session_date__lte=end_date)
    if venue_id:
        sessions = sessions.filter(venue_id=venue_id)

    venue_hours = {}
    for s in sessions:
        v_id = s.venue_id
        v_name = s.venue.name
        # Calculate duration in hours
        t_start = datetime.datetime.combine(s.session_date, s.session_start_time)
        t_end = datetime.datetime.combine(s.session_date, s.session_end_time)
        hours = max(0.0, (t_end - t_start).total_seconds() / 3600.0)

        if v_id not in venue_hours:
            venue_hours[v_id] = {"venue_id": v_id, "venue_name": v_name, "total_booked_hours": 0.0, "total_sessions": 0}
        venue_hours[v_id]["total_booked_hours"] += hours
        venue_hours[v_id]["total_sessions"] += 1

    breakdown = list(venue_hours.values())
    for item in breakdown:
        item["total_booked_hours"] = round(item["total_booked_hours"], 2)

    total_hours = sum(b["total_booked_hours"] for b in breakdown)

    return {
        "summary": {
            "total_venues": len(breakdown),
            "total_booked_hours": round(total_hours, 2),
        },
        "breakdown": breakdown,
    }


def get_discrepancy_frequency_analytics(
    user, start_date=None, end_date=None, venue_id=None, request_type=None, group_by="venue"
):
    """
    Computes discrepancy request frequencies grouped by venue or request type.
    """
    dept_qs = get_user_scope_departments(user)
    requests = DiscrepancyRequest.objects.filter(
        Q(proposed_venue__owning_department__in=dept_qs)
        | Q(timetable_entry__venue__owning_department__in=dept_qs)
        | Q(lecture_session__venue__owning_department__in=dept_qs)
    )

    if start_date:
        requests = requests.filter(created_at__date__gte=start_date)
    if end_date:
        requests = requests.filter(created_at__date__lte=end_date)
    if request_type:
        requests = requests.filter(request_type=request_type)
    if venue_id:
        requests = requests.filter(
            Q(proposed_venue_id=venue_id)
            | Q(timetable_entry__venue_id=venue_id)
            | Q(lecture_session__venue_id=venue_id)
        )

    total_requests = requests.count()
    by_status = dict(requests.values_list("status").annotate(count=Count("id")))
    by_type = dict(requests.values_list("request_type").annotate(count=Count("id")))

    return {
        "summary": {
            "total_discrepancies": total_requests,
            "by_status": by_status,
            "by_request_type": by_type,
        }
    }
