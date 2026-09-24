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
    user,
    start_date=None,
    end_date=None,
    department_id=None,
    faculty_id=None,
    course_id=None,
    level=None,
    program_id=None,
    lecturer_id=None,
    semester_id=None,
    group_by="week",
):
    """
    Computes lecture-hold rate analytics across past lecture sessions
    (accounting for held, not held, and unreported sessions)
    scoped to user authority level and grouped by week, course, program, lecturer, or department.
    """
    from scheduling.models import Semester

    dept_qs = get_user_scope_departments(user)
    fac_qs = get_user_scope_faculties(user)
    sch_qs = get_user_scope_schools(user)

    sessions = LectureSession.objects.filter(
        Q(timetable_entry__course__owning_department__in=dept_qs)
        | Q(timetable_entry__course__owning_faculty__in=fac_qs)
        | Q(timetable_entry__course__owning_school__in=sch_qs)
        | Q(venue__owning_department__in=dept_qs)
        | Q(venue__owning_faculty__in=fac_qs)
        | Q(venue__owning_school__in=sch_qs)
    ).exclude(
        status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED]
    ).distinct()

    # Past sessions up to today
    today = datetime.date.today()
    sessions = sessions.filter(session_date__lte=today)

    if start_date:
        sessions = sessions.filter(session_date__gte=start_date)
    if end_date:
        sessions = sessions.filter(session_date__lte=end_date)
    if semester_id:
        sessions = sessions.filter(timetable_entry__semester_id=semester_id)
    if department_id:
        sessions = sessions.filter(
            Q(timetable_entry__course__owning_department_id=department_id)
            | Q(venue__owning_department_id=department_id)
        )
    if faculty_id:
        sessions = sessions.filter(
            Q(timetable_entry__course__owning_faculty_id=faculty_id)
            | Q(timetable_entry__course__owning_department__faculty_id=faculty_id)
            | Q(venue__owning_faculty_id=faculty_id)
        )
    if course_id:
        sessions = sessions.filter(timetable_entry__course_id=course_id)
    if level:
        sessions = sessions.filter(timetable_entry__course__level=level)
    if program_id:
        sessions = sessions.filter(
            Q(timetable_entry__course__target_program_id=program_id)
            | (
                Q(timetable_entry__course__program_scope="general")
                & Q(timetable_entry__course__owning_department__programs__id=program_id)
            )
        )
    if lecturer_id:
        sessions = sessions.filter(timetable_entry__course__lecturers__id=lecturer_id)

    sessions = sessions.select_related(
        "report",
        "timetable_entry",
        "timetable_entry__course",
        "timetable_entry__course__owning_department",
        "timetable_entry__course__target_program",
        "timetable_entry__semester",
        "venue",
    ).prefetch_related(
        "timetable_entry__course__lecturers",
    ).distinct()

    # Resolve active semester for relative academic week calculation
    active_semester = None
    if semester_id:
        active_semester = Semester.objects.filter(id=semester_id).first()
    if not active_semester:
        active_semester = Semester.objects.filter(is_active=True).first()

    total_sessions = sessions.count()
    held_count = 0
    not_held_count = 0
    unreported_count = 0

    group_buckets = {}

    for s in sessions:
        # Determine reporting status
        report = getattr(s, "report", None)
        if report:
            is_held = report.held
            is_unreported = False
        elif s.status == LectureSession.Status.HELD:
            is_held = True
            is_unreported = False
        elif s.status == LectureSession.Status.NOT_HELD:
            is_held = False
            is_unreported = False
        else:
            is_held = False
            is_unreported = True

        if is_unreported:
            unreported_count += 1
        elif is_held:
            held_count += 1
        else:
            not_held_count += 1

        course = s.timetable_entry.course if s.timetable_entry else None
        c_code = course.code if course else (s.timetable_entry.title if s.timetable_entry else "N/A")
        c_title = course.title if course else ""

        # Determine grouping keys and payload
        if group_by == "lecturer":
            lecs = list(course.lecturers.all()) if course else []
            targets = lecs if lecs else [None]
            for lec in targets:
                if lec:
                    g_key = f"lec_{lec.id}"
                    g_label = lec.full_name
                    extra_data = {
                        "lecturer_id": str(lec.id),
                        "lecturer_name": lec.full_name,
                        "staff_id": lec.staff_id,
                        "department_name": lec.department.name if lec.department else "",
                    }
                else:
                    g_key = "unassigned"
                    g_label = "Unassigned"
                    extra_data = {
                        "lecturer_id": "unassigned",
                        "lecturer_name": "Unassigned Lecturer",
                        "staff_id": "-",
                        "department_name": "",
                    }
                if g_key not in group_buckets:
                    group_buckets[g_key] = {
                        "key": g_key,
                        "label": g_label,
                        "course_code": c_code,
                        "course_title": c_title,
                        "total_sessions": 0,
                        "held_count": 0,
                        "not_held_count": 0,
                        "unreported_count": 0,
                        **extra_data,
                    }
                bucket = group_buckets[g_key]
                bucket["total_sessions"] += 1
                if is_unreported:
                    bucket["unreported_count"] += 1
                elif is_held:
                    bucket["held_count"] += 1
                else:
                    bucket["not_held_count"] += 1
            continue

        elif group_by == "program":
            prog = course.target_program if course else None
            if prog:
                g_key = f"prog_{prog.id}"
                g_label = f"{prog.code} - {prog.name}"
                extra_data = {
                    "program_id": str(prog.id),
                    "program_name": prog.name,
                    "program_code": prog.code,
                }
            else:
                g_key = "general"
                g_label = "General / Core Courses"
                extra_data = {
                    "program_id": "general",
                    "program_name": "General / Departmental Courses",
                    "program_code": "GEN",
                }

        elif group_by == "department":
            dept = course.owning_department if course else None
            if dept:
                g_key = f"dept_{dept.id}"
                g_label = dept.name
                extra_data = {
                    "department_id": str(dept.id),
                    "department_name": dept.name,
                    "department_code": dept.code,
                }
            else:
                g_key = "other"
                g_label = "General / Faculty Courses"
                extra_data = {
                    "department_id": "other",
                    "department_name": "General / Faculty Courses",
                    "department_code": "GEN",
                }

        elif group_by == "course":
            g_key = str(course.id) if course else c_code
            g_label = f"{c_code} - {c_title}" if c_title else c_code
            extra_data = {
                "course_id": str(course.id) if course else "",
                "course_code": c_code,
                "course_title": c_title,
                "level": course.level if course else None,
            }

        elif group_by in ["day", "date"]:
            g_key = s.session_date.isoformat()
            g_label = s.session_date.strftime("%b %d")
            extra_data = {"date": s.session_date.isoformat()}

        elif group_by == "month":
            g_key = s.session_date.strftime("%Y-%m")
            g_label = s.session_date.strftime("%b %Y")
            extra_data = {"month": s.session_date.strftime("%Y-%m")}

        else:
            # Default "week" (calculated relative to semester lecture start)
            sem = s.timetable_entry.semester or active_semester
            lec_start = sem.lecture_start_date or sem.start_date if sem else None
            if lec_start:
                start_monday = lec_start - datetime.timedelta(days=lec_start.weekday())
                diff_days = (s.session_date - start_monday).days
                week_num = max(1, (diff_days // 7) + 1)
                if sem and sem.duration_value:
                    week_num = min(week_num, sem.duration_value)
                w_start = start_monday + datetime.timedelta(days=(week_num - 1) * 7)
                w_end = w_start + datetime.timedelta(days=6)
                g_key = f"week_{week_num:02d}"
                g_label = f"Week {week_num}"
                extra_data = {
                    "week_number": week_num,
                    "date_range": f"{w_start.strftime('%d/%m')} - {w_end.strftime('%d/%m')}",
                }
            else:
                year, week_num, _ = s.session_date.isocalendar()
                g_key = f"{year}-W{week_num:02d}"
                g_label = f"Wk {week_num}"
                extra_data = {"week_number": week_num}

        if g_key not in group_buckets:
            group_buckets[g_key] = {
                "key": g_key,
                "label": g_label,
                "course_code": c_code,
                "course_title": c_title,
                "total_sessions": 0,
                "held_count": 0,
                "not_held_count": 0,
                "unreported_count": 0,
                **extra_data,
            }

        bucket = group_buckets[g_key]
        bucket["total_sessions"] += 1
        if is_unreported:
            bucket["unreported_count"] += 1
        elif is_held:
            bucket["held_count"] += 1
        else:
            bucket["not_held_count"] += 1

    breakdown = []
    # Sort buckets chronologically by key
    for b in sorted(group_buckets.values(), key=lambda x: x["key"]):
        h = b["held_count"]
        nh = b["not_held_count"]
        reported = h + nh
        b["hold_rate_percentage"] = round((h / reported) * 100, 1) if reported > 0 else 0.0
        breakdown.append(b)

    total_reported = held_count + not_held_count
    hold_rate_percentage = round((held_count / total_reported) * 100, 1) if total_reported > 0 else 0.0

    return {
        "summary": {
            "total_reports": total_reported,
            "total_sessions": total_sessions,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "unreported_count": unreported_count,
            "hold_rate_percentage": hold_rate_percentage,
        },
        "breakdown": breakdown,
    }


def get_venue_utilization_analytics(
    user, start_date=None, end_date=None, department_id=None, venue_id=None, group_by="venue"
):
    """
    Computes venue utilization hours for lectures across venues in user scope,
    optionally narrowed per department.
    """
    dept_qs = get_user_scope_departments(user)
    fac_qs = get_user_scope_faculties(user)
    sch_qs = get_user_scope_schools(user)

    sessions = LectureSession.objects.filter(
        Q(venue__owning_department__in=dept_qs)
        | Q(venue__owning_faculty__in=fac_qs)
        | Q(venue__owning_school__in=sch_qs)
    ).exclude(
        status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED]
    )

    if start_date:
        sessions = sessions.filter(session_date__gte=start_date)
    if end_date:
        sessions = sessions.filter(session_date__lte=end_date)
    if department_id:
        sessions = sessions.filter(venue__owning_department_id=department_id)
    if venue_id:
        sessions = sessions.filter(venue_id=venue_id)

    venue_hours = {}
    for s in sessions:
        v_id = s.venue_id
        v_name = s.venue.name
        t_start = datetime.datetime.combine(s.session_date, s.session_start_time)
        t_end = datetime.datetime.combine(s.session_date, s.session_end_time)
        hours = max(0.0, (t_end - t_start).total_seconds() / 3600.0)

        if v_id not in venue_hours:
            venue_hours[v_id] = {
                "venue_id": v_id,
                "venue_name": v_name,
                "total_booked_hours": 0.0,
                "total_sessions": 0,
            }
        venue_hours[v_id]["total_booked_hours"] += hours
        venue_hours[v_id]["total_sessions"] += 1

    breakdown = list(venue_hours.values())
    for item in breakdown:
        item["total_booked_hours"] = round(item["total_booked_hours"], 1)

    # Sort descending by booked hours
    breakdown.sort(key=lambda x: x["total_booked_hours"], reverse=True)

    total_hours = sum(b["total_booked_hours"] for b in breakdown)

    return {
        "summary": {
            "total_venues": len(breakdown),
            "total_booked_hours": round(total_hours, 1),
        },
        "breakdown": breakdown,
    }


def get_discrepancy_frequency_analytics(
    user, start_date=None, end_date=None, venue_id=None, request_type=None, group_by="venue"
):
    """
    Computes discrepancy request frequencies grouped by status and request type,
    scoped to user authority level.
    """
    from accounts.models import AdminOfficer
    from hierarchy.models import Department, Faculty

    requests = DiscrepancyRequest.objects.all()

    admin_prof = getattr(user, "admin_profile", None)
    if not (user.is_superuser or (user.is_staff and not admin_prof)):
        if not admin_prof:
            requests = DiscrepancyRequest.objects.none()
        elif admin_prof.level == AdminOfficer.Level.DEPARTMENT:
            dept_qs = get_user_scope_departments(user)
            requests = requests.filter(
                Q(initiated_by=user)
                | Q(routed_to=admin_prof)
                | Q(proposed_venue__owning_department__in=dept_qs)
                | Q(timetable_entry__venue__owning_department__in=dept_qs)
                | Q(timetable_entry__course__owning_department__in=dept_qs)
            )
        elif admin_prof.level == AdminOfficer.Level.FACULTY:
            if admin_prof.scope_faculty:
                dept_ids = Department.objects.filter(faculty=admin_prof.scope_faculty).values_list("id", flat=True)
                requests = requests.filter(
                    Q(initiated_by=user)
                    | Q(routed_to=admin_prof)
                    | Q(routed_to__scope_department_id__in=dept_ids)
                    | Q(initiated_by__admin_profile__scope_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_faculty=admin_prof.scope_faculty)
                    | Q(timetable_entry__course__owning_department_id__in=dept_ids)
                )
            else:
                requests = requests.filter(Q(initiated_by=user) | Q(routed_to=admin_prof))
        elif admin_prof.level == AdminOfficer.Level.SCHOOL:
            if admin_prof.scope_school:
                dept_ids = Department.objects.filter(faculty__school=admin_prof.scope_school).values_list("id", flat=True)
                fac_ids = Faculty.objects.filter(school=admin_prof.scope_school).values_list("id", flat=True)
                requests = requests.filter(
                    Q(initiated_by=user)
                    | Q(routed_to=admin_prof)
                    | Q(routed_to__scope_faculty_id__in=fac_ids)
                    | Q(routed_to__scope_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_department_id__in=dept_ids)
                    | Q(proposed_venue__owning_faculty_id__in=fac_ids)
                    | Q(proposed_venue__owning_school=admin_prof.scope_school)
                    | Q(timetable_entry__course__owning_department_id__in=dept_ids)
                )
            else:
                requests = requests.filter(Q(initiated_by=user) | Q(routed_to=admin_prof))

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
        )

    requests = requests.distinct()
    total_requests = requests.count()

    by_status = {
        "approved": requests.filter(status__in=[DiscrepancyRequest.Status.APPROVED, DiscrepancyRequest.Status.APPLIED]).count(),
        "rejected": requests.filter(status=DiscrepancyRequest.Status.REJECTED).count(),
        "pending": requests.filter(status=DiscrepancyRequest.Status.PENDING).count(),
        "withdrawn": requests.filter(status=DiscrepancyRequest.Status.WITHDRAWN).count(),
    }
    by_type = dict(requests.values_list("request_type").annotate(count=Count("id")))

    return {
        "summary": {
            "total_discrepancies": total_requests,
            "by_status": by_status,
            "by_request_type": by_type,
        }
    }
