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

from django.utils import timezone
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
            timetable_entry__course__owning_department_id=department_id
        )
    if faculty_id:
        sessions = sessions.filter(
            Q(timetable_entry__course__owning_faculty_id=faculty_id)
            | Q(timetable_entry__course__owning_department__faculty_id=faculty_id)
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
        "timetable_entry__course__owning_faculty",
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

    now = timezone.now()
    held_count = 0
    not_held_count = 0
    unreported_count = 0

    group_buckets = {}

    # Pre-initialize buckets for hierarchical groups so all entities appear
    if group_by == "faculty":
        from hierarchy.models import Faculty
        target_facs = fac_qs if fac_qs.exists() else Faculty.objects.filter(school__in=sch_qs)
        for f in target_facs:
            g_key = f"fac_{f.id}"
            group_buckets[g_key] = {
                "key": g_key,
                "label": f.name,
                "faculty_id": str(f.id),
                "faculty_name": f.name,
                "faculty_code": f.code,
                "total_sessions": 0,
                "held_count": 0,
                "not_held_count": 0,
                "unreported_count": 0,
            }
    elif group_by == "department":
        from hierarchy.models import Department
        target_depts = Department.objects.filter(id__in=dept_qs.values_list("id", flat=True))
        if faculty_id:
            target_depts = target_depts.filter(faculty_id=faculty_id)
        for d in target_depts:
            g_key = f"dept_{d.id}"
            group_buckets[g_key] = {
                "key": g_key,
                "label": d.name,
                "department_id": str(d.id),
                "department_name": d.name,
                "department_code": d.code,
                "total_sessions": 0,
                "held_count": 0,
                "not_held_count": 0,
                "unreported_count": 0,
            }
    elif group_by == "program":
        from hierarchy.models import Program
        dept_ids = []
        if department_id:
            dept_ids = [department_id]
        elif dept_qs.exists():
            dept_ids = list(dept_qs.values_list("id", flat=True))

        target_progs = Program.objects.filter(department_id__in=dept_ids) if dept_ids else Program.objects.none()
        for p in target_progs:
            g_key = f"prog_{p.id}"
            group_buckets[g_key] = {
                "key": g_key,
                "label": f"{p.code} - {p.name}",
                "program_id": str(p.id),
                "program_name": p.name,
                "program_code": p.code,
                "total_sessions": 0,
                "held_count": 0,
                "not_held_count": 0,
                "unreported_count": 0,
            }

    for s in sessions:
        # Check if the schedule's datetime has already passed
        session_dt = datetime.datetime.combine(s.session_date, s.session_end_time)
        if timezone.is_naive(session_dt):
            session_dt = timezone.make_aware(session_dt)

        is_past = session_dt <= now

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
        elif is_past:
            # The schedule is in the past and has no report submitted
            is_held = False
            is_unreported = True
        else:
            # Future schedule whose datetime has not passed yet
            continue

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

        elif group_by == "faculty":
            fac = None
            if course:
                fac = course.owning_faculty or (course.owning_department.faculty if course.owning_department else None)
            if fac:
                g_key = f"fac_{fac.id}"
                g_label = fac.name
                extra_data = {
                    "faculty_id": str(fac.id),
                    "faculty_name": fac.name,
                    "faculty_code": fac.code,
                }
            else:
                g_key = "general"
                g_label = "General / School Courses"
                extra_data = {
                    "faculty_id": "general",
                    "faculty_name": "General / School Courses",
                    "faculty_code": "GEN",
                }

        elif group_by == "program":
            prog = course.target_program if course else None
            if not prog and course and course.owning_department_id:
                dept_programs = list(course.owning_department.programs.all())
                c_code_clean = (course.code or "").upper().replace("-", "")
                for p in dept_programs:
                    p_prefix = p.code.upper().replace("GEN", "")
                    if p_prefix and (c_code_clean.startswith(p_prefix) or p_prefix in c_code_clean):
                        prog = p
                        break
                if not prog:
                    dept_code = (course.owning_department.code or "").upper()
                    if c_code_clean.startswith(dept_code) or c_code_clean.startswith("COS") or c_code_clean.startswith("CSC"):
                        prog = next((p for p in dept_programs if p.is_default), dept_programs[0] if dept_programs else None)

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
                    "program_name": "General / Core Courses",
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

    total_past_sessions = held_count + not_held_count + unreported_count
    total_reported = held_count + not_held_count
    hold_rate_percentage = round((held_count / total_reported) * 100, 1) if total_reported > 0 else 0.0

    return {
        "summary": {
            "total_reports": total_reported,
            "total_sessions": total_past_sessions,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "unreported_count": unreported_count,
            "hold_rate_percentage": hold_rate_percentage,
        },
        "breakdown": breakdown,
    }


def get_venue_utilization_analytics(
    user,
    start_date=None,
    end_date=None,
    department_id=None,
    faculty_id=None,
    venue_id=None,
    semester_id=None,
    group_by="venue",
    faculty_owned_only=False,
):
    """
    Computes venue utilization hours for lectures across venues in user scope,
    optionally narrowed per department, faculty-owned venues alone, or grouped per faculty.
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
    ).select_related(
        "venue",
        "venue__owning_department",
        "venue__owning_faculty",
        "venue__owning_department__faculty",
    )

    if start_date:
        sessions = sessions.filter(session_date__gte=start_date)
    if end_date:
        sessions = sessions.filter(session_date__lte=end_date)
    if semester_id:
        sessions = sessions.filter(timetable_entry__semester_id=semester_id)

    if faculty_owned_only:
        sessions = sessions.filter(
            venue__owning_level="faculty",
            venue__owning_department__isnull=True,
        )
        if faculty_id:
            sessions = sessions.filter(venue__owning_faculty_id=faculty_id)
        elif fac_qs.exists():
            sessions = sessions.filter(venue__owning_faculty__in=fac_qs)
    else:
        if faculty_id:
            sessions = sessions.filter(
                Q(venue__owning_faculty_id=faculty_id)
                | Q(venue__owning_department__faculty_id=faculty_id)
            )
        if department_id:
            sessions = sessions.filter(venue__owning_department_id=department_id)

    if venue_id:
        sessions = sessions.filter(venue_id=venue_id)

    if group_by == "faculty":
        from hierarchy.models import Faculty
        faculty_hours = {}
        # Pre-initialize faculties in scope so all faculties appear
        target_facs = fac_qs if fac_qs.exists() else Faculty.objects.filter(school__in=sch_qs)
        for f in target_facs:
            faculty_hours[str(f.id)] = {
                "faculty_id": str(f.id),
                "faculty_name": f.name,
                "faculty_code": f.code,
                "total_booked_hours": 0.0,
                "total_sessions": 0,
            }

        for s in sessions:
            fac = s.venue.owning_faculty or (
                s.venue.owning_department.faculty if s.venue.owning_department else None
            )
            fac_id = str(fac.id) if fac else "other"
            fac_name = fac.name if fac else "General / School Venues"
            t_start = datetime.datetime.combine(s.session_date, s.session_start_time)
            t_end = datetime.datetime.combine(s.session_date, s.session_end_time)
            hours = max(0.0, (t_end - t_start).total_seconds() / 3600.0)

            if fac_id not in faculty_hours:
                faculty_hours[fac_id] = {
                    "faculty_id": fac_id,
                    "faculty_name": fac_name,
                    "faculty_code": fac.code if fac else "GEN",
                    "total_booked_hours": 0.0,
                    "total_sessions": 0,
                }
            faculty_hours[fac_id]["total_booked_hours"] += hours
            faculty_hours[fac_id]["total_sessions"] += 1

        breakdown = list(faculty_hours.values())
        for item in breakdown:
            item["total_booked_hours"] = round(item["total_booked_hours"], 1)

        breakdown.sort(key=lambda x: x["total_booked_hours"], reverse=True)
        total_hours = sum(b["total_booked_hours"] for b in breakdown)

        return {
            "summary": {
                "total_faculties": len(breakdown),
                "total_booked_hours": round(total_hours, 1),
            },
            "breakdown": breakdown,
        }

    venue_hours = {}
    target_venues = None
    if faculty_owned_only:
        target_venues = Venue.objects.filter(
            owning_level="faculty",
            owning_department__isnull=True,
            is_active=True,
        )
        if faculty_id:
            target_venues = target_venues.filter(owning_faculty_id=faculty_id)
        elif fac_qs.exists():
            target_venues = target_venues.filter(owning_faculty__in=fac_qs)
    elif department_id:
        target_venues = Venue.objects.filter(
            owning_department_id=department_id,
            is_active=True,
        )

    if target_venues is not None:
        for v in target_venues:
            venue_hours[v.id] = {
                "venue_id": v.id,
                "venue_name": v.name,
                "total_booked_hours": 0.0,
                "total_sessions": 0,
            }

    for s in sessions:
        v_id = s.venue_id
        v_name = s.venue.name if s.venue else "Unknown Venue"
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


def get_dashboard_statcards(user):
    """
    Returns role-based dashboard statcards:
    - System admin:
      * Active Venues (entire system: all schools combined)
      * Total number of schools
      * Total hard conflicts
      * System Quality score (overall quality score calculated from a weighted calculation of the conflicts / constraints)
    - School admin:
      * Active venues in school
      * Total number of faculties
      * Total lecture hold-rate for semester (entire school)
    - Faculty admin:
      * Active venues in faculty
      * Total number of departments
      * Total lecture hold-rate for semester (entire faculty)
    - Department admin:
      * Active venues in department
      * Total number of courses in semester
      * Discrepancy Queue
      * Total unreported sessions (this week)
    """
    from scheduling.models import Semester, TimetableEntry, TimetableGenerationRun, LectureSession
    from hierarchy.models import School, Faculty, Department
    from courses.models import Course
    from venues.models import Venue
    from discrepancies.models import DiscrepancyRequest

    admin_prof = getattr(user, "admin_profile", None)
    if user.is_superuser or (admin_prof and admin_prof.level in ["system", "university"]):
        role_level = "system"
    elif admin_prof and admin_prof.level == "school":
        role_level = "school"
    elif admin_prof and admin_prof.level == "faculty":
        role_level = "faculty"
    elif admin_prof and admin_prof.level == "department":
        role_level = "department"
    else:
        role_level = "system" if user.is_staff else "department"

    active_semester = Semester.objects.filter(is_active=True).first() or Semester.objects.first()
    active_semester_id = active_semester.id if active_semester else None

    if role_level == "system":
        active_venues = Venue.objects.filter(is_active=True).count()
        total_schools = School.objects.count()

        # Hard conflicts from latest completed generation runs per scope or live entries
        gen_runs = TimetableGenerationRun.objects.filter(status=TimetableGenerationRun.Status.COMPLETED)
        if active_semester:
            gen_runs = gen_runs.filter(semester=active_semester)

        latest_runs = {}
        for run in gen_runs.order_by("-created_at"):
            key = (run.scope_type, run.scope_id)
            if key not in latest_runs:
                latest_runs[key] = run

        if latest_runs:
            hard_conflicts = sum(r.hard_conflicts_count for r in latest_runs.values())
            total_weight = 0
            weighted_quality = 0.0
            for r in latest_runs.values():
                w = max(1, r.hard_conflicts_count + r.student_conflicts_count + 10)
                q = None
                if isinstance(r.generation_metrics, dict):
                    q = r.generation_metrics.get("quality_score")
                if q is None:
                    q = r.fitness_score if r.fitness_score > 0 else (
                        0.95 if r.hard_conflicts_count == 0 else max(0.0, 0.85 - (r.hard_conflicts_count * 0.05))
                    )
                weighted_quality += float(q) * w
                total_weight += w
            system_quality_val = round((weighted_quality / max(1, total_weight)) * 100, 1)
        else:
            entries = TimetableEntry.objects.all()
            if active_semester:
                entries = entries.filter(semester=active_semester)
            venue_clashes = entries.values("venue_id", "start_time", "end_time", "recurrence_rule").annotate(c=Count("id")).filter(c__gt=1)
            hard_conflicts = venue_clashes.count()
            if hard_conflicts == 0:
                system_quality_val = 98.5
            else:
                system_quality_val = max(10.0, round(100.0 - (hard_conflicts * 4.5), 1))

        cards = [
            {
                "id": "active_venues",
                "title": "Active Venues",
                "value": active_venues,
                "unit": "Venues",
                "badge": "All Schools",
                "badge_variant": "success",
                "description": "Entire system: all schools combined",
            },
            {
                "id": "total_schools",
                "title": "Total Schools",
                "value": total_schools,
                "unit": "Schools",
                "badge": "Institutional",
                "badge_variant": "neutral",
                "description": "Total academic schools in system",
            },
            {
                "id": "hard_conflicts",
                "title": "Total Hard Conflicts",
                "value": hard_conflicts,
                "unit": "Conflicts",
                "badge": "Zero Conflict" if hard_conflicts == 0 else "Action Required",
                "badge_variant": "success" if hard_conflicts == 0 else "danger",
                "description": "Cross-venue and instructor collisions",
            },
            {
                "id": "quality_score",
                "title": "System Quality Score",
                "value": f"{system_quality_val}%",
                "unit": "Quality",
                "badge": "Optimal" if system_quality_val >= 90 else ("Good" if system_quality_val >= 75 else "Needs Review"),
                "badge_variant": "success" if system_quality_val >= 90 else ("warning" if system_quality_val >= 75 else "danger"),
                "description": "Weighted conflict & constraint optimization",
            },
        ]

    elif role_level == "school":
        school = admin_prof.scope_school if admin_prof else None
        if school:
            active_venues = Venue.objects.filter(is_active=True).filter(
                Q(owning_school=school)
                | Q(owning_faculty__school=school)
                | Q(owning_department__faculty__school=school)
            ).distinct().count()
            total_faculties = Faculty.objects.filter(school=school).count()
        else:
            active_venues = Venue.objects.filter(is_active=True).count()
            total_faculties = Faculty.objects.count()

        hold_rate_res = get_lecture_hold_rate_analytics(
            user=user,
            semester_id=active_semester_id,
        )
        hold_rate_pct = hold_rate_res.get("summary", {}).get("hold_rate_percentage", 0)

        cards = [
            {
                "id": "active_venues",
                "title": "Active Venues in School",
                "value": active_venues,
                "unit": "Venues",
                "badge": getattr(school, "code", "School Scope"),
                "badge_variant": "success",
                "description": "Venues in this school",
            },
            {
                "id": "total_faculties",
                "title": "Total Faculties",
                "value": total_faculties,
                "unit": "Faculties",
                "badge": "Constituent",
                "badge_variant": "neutral",
                "description": "Faculties under this school",
            },
            {
                "id": "hold_rate",
                "title": "Semester Hold Rate",
                "value": f"{hold_rate_pct}%",
                "unit": "Hold Rate",
                "badge": "Optimal" if hold_rate_pct >= 75 else ("Fair" if hold_rate_pct >= 50 else "Critical"),
                "badge_variant": "success" if hold_rate_pct >= 75 else ("warning" if hold_rate_pct >= 50 else "danger"),
                "description": "Total lecture hold-rate for semester (entire school)",
            },
        ]

    elif role_level == "faculty":
        faculty = admin_prof.scope_faculty if admin_prof else None
        if faculty:
            active_venues = Venue.objects.filter(is_active=True).filter(
                Q(owning_faculty=faculty)
                | Q(owning_department__faculty=faculty)
            ).distinct().count()
            total_departments = Department.objects.filter(faculty=faculty).count()
        else:
            active_venues = Venue.objects.filter(is_active=True).count()
            total_departments = Department.objects.count()

        hold_rate_res = get_lecture_hold_rate_analytics(
            user=user,
            faculty_id=str(faculty.id) if faculty else None,
            semester_id=active_semester_id,
        )
        hold_rate_pct = hold_rate_res.get("summary", {}).get("hold_rate_percentage", 0)

        cards = [
            {
                "id": "active_venues",
                "title": "Active Venues in Faculty",
                "value": active_venues,
                "unit": "Venues",
                "badge": getattr(faculty, "code", "Faculty Scope"),
                "badge_variant": "success",
                "description": "Venues in this faculty",
            },
            {
                "id": "total_departments",
                "title": "Total Departments",
                "value": total_departments,
                "unit": "Departments",
                "badge": "Academic Units",
                "badge_variant": "neutral",
                "description": "Departments under this faculty",
            },
            {
                "id": "hold_rate",
                "title": "Semester Hold Rate",
                "value": f"{hold_rate_pct}%",
                "unit": "Hold Rate",
                "badge": "Optimal" if hold_rate_pct >= 75 else ("Fair" if hold_rate_pct >= 50 else "Critical"),
                "badge_variant": "success" if hold_rate_pct >= 75 else ("warning" if hold_rate_pct >= 50 else "danger"),
                "description": "Total lecture hold-rate for semester (entire faculty)",
            },
        ]

    else:  # Department Admin
        dept = admin_prof.scope_department if admin_prof else None
        if dept:
            active_venues = Venue.objects.filter(is_active=True).filter(
                Q(owning_department=dept) | Q(timetable_entries__course__owning_department=dept)
            ).distinct().count()
            courses_qs = Course.objects.filter(owning_department=dept)
            if active_semester:
                courses_qs = courses_qs.filter(semester=active_semester)
            total_courses = courses_qs.count()
            discrepancy_queue = DiscrepancyRequest.objects.filter(
                status=DiscrepancyRequest.Status.PENDING,
                timetable_entry__course__owning_department=dept,
            ).distinct().count()
        else:
            active_venues = Venue.objects.filter(is_active=True).count()
            courses_qs = Course.objects.all()
            if active_semester:
                courses_qs = courses_qs.filter(semester=active_semester)
            total_courses = courses_qs.count()
            discrepancy_queue = DiscrepancyRequest.objects.filter(status=DiscrepancyRequest.Status.PENDING).count()

        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        unreported_qs = LectureSession.objects.filter(
            session_date__range=(week_start, today),
            report__isnull=True,
        ).exclude(
            status__in=[
                LectureSession.Status.CANCELLED,
                LectureSession.Status.POSTPONED,
                LectureSession.Status.HELD,
                LectureSession.Status.NOT_HELD,
            ]
        )
        if dept:
            unreported_qs = unreported_qs.filter(timetable_entry__course__owning_department=dept)
        unreported_this_week = unreported_qs.distinct().count()

        cards = [
            {
                "id": "active_venues",
                "title": "Active Venues",
                "value": active_venues,
                "unit": "Venues",
                "badge": getattr(dept, "code", "Dept Scope"),
                "badge_variant": "success",
                "description": "Active venues in department",
            },
            {
                "id": "total_courses",
                "title": "Total Courses in Semester",
                "value": total_courses,
                "unit": "Courses",
                "badge": "Semester Scope",
                "badge_variant": "neutral",
                "description": "Department course offerings",
            },
            {
                "id": "discrepancy_queue",
                "title": "Discrepancy Queue",
                "value": discrepancy_queue,
                "unit": "Pending",
                "badge": "Requires Action" if discrepancy_queue > 0 else "Queue Clear",
                "badge_variant": "warning" if discrepancy_queue > 0 else "success",
                "description": "Pending requests requiring resolution",
            },
            {
                "id": "unreported_sessions",
                "title": "Unreported Sessions (This Week)",
                "value": unreported_this_week,
                "unit": "Sessions",
                "badge": "Audit Required" if unreported_this_week > 0 else "Up to Date",
                "badge_variant": "danger" if unreported_this_week > 0 else "success",
                "description": "Sessions this week awaiting rep report",
            },
        ]

    return {
        "role_level": role_level,
        "cards": cards,
    }


def get_venue_capacity_deficit_analytics(user, semester_id=None):
    """
    Computes average venue capacity deficit for School, Faculty, and Department admins.
    Excludes System Admin (is_applicable=False).
    """
    admin_prof = getattr(user, "admin_profile", None)
    if user.is_superuser or (admin_prof and admin_prof.level in ["system", "university"]):
        return {
            "role_level": "system",
            "is_applicable": False,
            "message": "System Administrator oversees all schools. Capacity deficit is monitored at school, faculty, and department levels.",
        }

    dept_qs = get_user_scope_departments(user)
    from scheduling.models import Semester, TimetableEntry
    from student_counts.models import ProgramStudentCount

    if not semester_id:
        active_semester = Semester.objects.filter(is_active=True).first() or Semester.objects.first()
        semester_id = active_semester.id if active_semester else None

    entries_qs = TimetableEntry.objects.filter(
        course__owning_department__in=dept_qs
    ).select_related("venue", "course", "course__target_program", "course__owning_department")
    if semester_id:
        entries_qs = entries_qs.filter(semester_id=semester_id)

    counts_map = {}
    for sc in ProgramStudentCount.objects.select_related("program"):
        counts_map[(sc.program_id, sc.level)] = sc.count

    total_analyzed = 0
    deficits = []
    overcrowded_count = 0

    for entry in entries_qs:
        venue = entry.venue
        if not venue or not venue.capacity:
            continue

        course = entry.course
        cohort_size = 50
        if course:
            if course.target_program_id and (course.target_program_id, course.level) in counts_map:
                cohort_size = counts_map[(course.target_program_id, course.level)]
            elif course.owning_department_id:
                matching = [c for (p_id, lvl), c in counts_map.items() if lvl == course.level]
                if matching:
                    cohort_size = int(sum(matching) / len(matching))

        deficit = max(0, cohort_size - venue.capacity)
        deficits.append(deficit)
        total_analyzed += 1
        if deficit > 0:
            overcrowded_count += 1

    if total_analyzed == 0 or len(deficits) == 0:
        avg_deficit = 0.0
        peak_deficit = 0
        overcrowd_pct = 0.0
    else:
        avg_deficit = round(sum(deficits) / total_analyzed, 1)
        peak_deficit = max(deficits, default=0)
        overcrowd_pct = round((overcrowded_count / total_analyzed) * 100, 1)

    scope_name = "Scope"
    if admin_prof:
        if admin_prof.level == "school" and admin_prof.scope_school:
            scope_name = admin_prof.scope_school.name
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty:
            scope_name = admin_prof.scope_faculty.name
        elif admin_prof.level == "department" and admin_prof.scope_department:
            scope_name = admin_prof.scope_department.name

    if avg_deficit == 0 or overcrowded_count == 0:
        status_variant = "success"
        remark = f"Optimal Capacity — All allocated venues in {scope_name} adequately accommodate expected cohort enrollments with zero seating shortfall."
    elif avg_deficit <= 15:
        status_variant = "warning"
        remark = f"Moderate Deficit — Venues in {scope_name} experience an average seating deficit of {avg_deficit} seats across {overcrowded_count} scheduled session(s). Minor room reassignments or secondary seating recommended."
    else:
        status_variant = "danger"
        remark = f"Critical Capacity Deficit — Severe overcrowding detected in {scope_name} with an average deficit of {avg_deficit} seats per session (peak deficit: {peak_deficit} seats). Immediate venue upgrades or section splitting required."

    return {
        "role_level": admin_prof.level if admin_prof else "department",
        "is_applicable": True,
        "scope_name": scope_name,
        "average_deficit": avg_deficit,
        "peak_deficit": peak_deficit,
        "total_sessions_analyzed": total_analyzed,
        "overcrowded_sessions_count": overcrowded_count,
        "overcrowding_percentage": overcrowd_pct,
        "case_aware_remark": remark,
        "status_variant": status_variant,
    }
