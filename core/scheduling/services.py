import datetime
from django.db import transaction
from django.db.models import Q
from hierarchy.models import Department, Faculty, Program, School
from accounts.permissions import (
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from .models import LectureSession


WEEKDAY_MAP = {
    "monday": 0, "mon": 0, "mo": 0, "0": 0,
    "tuesday": 1, "tue": 1, "tu": 1, "1": 1,
    "wednesday": 2, "wed": 2, "we": 2, "2": 2,
    "thursday": 3, "thu": 3, "th": 3, "3": 3,
    "friday": 4, "fri": 4, "fr": 4, "4": 4,
    "saturday": 5, "sat": 5, "sa": 5, "5": 5,
    "sunday": 6, "sun": 6, "su": 6, "6": 6,
}


def parse_target_weekdays(rule_str):
    """
    Parses recurrence rule strings like:
    - 'FREQ=WEEKLY;BYDAY=MO,WE' or 'BYDAY=TH'
    - 'weekly:tuesday', 'weekly:mon,wed,fri', or 'tuesday'
    Returns a set of integer weekdays (0=Monday .. 6=Sunday).
    """
    if not rule_str:
        return set()

    rule_clean = rule_str.strip().lower()

    if "byday=" in rule_clean:
        day_part = rule_clean.split("byday=")[1].split(";")[0]
    elif ":" in rule_clean:
        parts = rule_clean.split(":")
        day_part = parts[-1]
    else:
        day_part = rule_clean

    target_days = set()
    for token in day_part.replace(",", " ").split():
        token = token.strip()
        if token in WEEKDAY_MAP:
            target_days.add(WEEKDAY_MAP[token])
        else:
            for key, val in WEEKDAY_MAP.items():
                if len(key) >= 3 and key in token:
                    target_days.add(val)
                    break
    return target_days


@transaction.atomic
def materialize_timetable_entry(entry):
    """
    Expands a recurring TimetableEntry into dated LectureSession rows between
    recurrence_start_date and recurrence_end_date.
    """
    if not entry.recurrence_rule or not entry.recurrence_start_date or not entry.recurrence_end_date:
        return []

    target_weekdays = parse_target_weekdays(entry.recurrence_rule)
    if not target_weekdays:
        return []

    created_sessions = []
    current_date = entry.recurrence_start_date
    end_date = entry.recurrence_end_date

    while current_date <= end_date:
        if current_date.weekday() in target_weekdays:
            session, created = LectureSession.objects.get_or_create(
                timetable_entry=entry,
                session_date=current_date,
                defaults={
                    "session_start_time": entry.start_time,
                    "session_end_time": entry.end_time,
                    "venue": entry.venue,
                    "status": entry.status if entry.status in dict(LectureSession.Status.choices) else LectureSession.Status.SCHEDULED,
                },
            )
            created_sessions.append(session)
        current_date += datetime.timedelta(days=1)

    return created_sessions


def get_effective_exam_period(semester, faculty=None, department=None):
    """
    Resolves the effective (start_date, end_date, source, period_obj) for the exam period.
    - If faculty is given (or resolved from department):
      Check if GenerationScopePermission allows faculty exam period for the school.
      If allowed, check if a FacultyExamPeriod exists for (semester, faculty).
      If found, return (fep.start_date, fep.end_date, "faculty", fep).
    - Otherwise, fallback to semester.exam_start_date, semester.exam_end_date, "school", None if set.
    - If neither is set, return (None, None, "none", None).
    """
    if not semester:
        return None, None, "none", None

    school = semester.session.school if semester.session else None

    # Resolve target faculty
    target_faculty = faculty
    if not target_faculty and department:
        target_faculty = department.faculty

    if target_faculty and school:
        from .models import GenerationScopePermission, FacultyExamPeriod
        perm = GenerationScopePermission.objects.filter(school=school).first()
        if perm and perm.allow_faculty_exam_period:
            fep = FacultyExamPeriod.objects.filter(semester=semester, faculty=target_faculty).first()
            if fep and fep.start_date and fep.end_date:
                return fep.start_date, fep.end_date, "faculty", fep

    if semester.exam_start_date and semester.exam_end_date:
        return semester.exam_start_date, semester.exam_end_date, "school", None

    return None, None, "none", None


def build_timetable_scope_q(user, prefix=""):
    """
    Constructs a Q filter restricting TimetableEntry or LectureSession querysets
    to the courses, venues, access grants, and events visible to the given user.

    Supports prefix="" for TimetableEntry and prefix="timetable_entry__" for LectureSession.
    """
    p = prefix
    if not user.is_authenticated:
        return Q(pk__in=[])

    if user.is_superuser or (user.is_staff and not hasattr(user, "admin_profile")):
        return Q()

    profile = getattr(user, "admin_profile", None)
    if profile:
        if profile.level in ["system", "university"]:
            return Q()

        if profile.level == "school" and profile.scope_school_id:
            sch_id = profile.scope_school_id
            venue_q = (
                Q(venue__owning_school_id=sch_id)
                | Q(venue__owning_faculty__school_id=sch_id)
                | Q(venue__owning_department__faculty__school_id=sch_id)
            )
            if p:
                venue_q |= (
                    Q(**{f"{p}venue__owning_school_id": sch_id})
                    | Q(**{f"{p}venue__owning_faculty__school_id": sch_id})
                    | Q(**{f"{p}venue__owning_department__faculty__school_id": sch_id})
                )
            return (
                Q(**{f"{p}course__owning_school_id": sch_id})
                | Q(**{f"{p}course__owning_faculty__school_id": sch_id})
                | Q(**{f"{p}course__owning_department__faculty__school_id": sch_id})
                | venue_q
                | Q(**{f"{p}course__access_grants__granted_to_school_id": sch_id, f"{p}course__access_grants__status": "approved"})
                | Q(**{f"{p}course__owning_level": "general"})
                | Q(**{f"{p}entry_type": "event"})
            )

        if profile.level == "faculty" and profile.scope_faculty_id:
            fac_id = profile.scope_faculty_id
            return build_faculty_timetable_q(fac_id, prefix=prefix)

        if profile.level == "department" and profile.scope_department_id:
            dept_id = profile.scope_department_id
            return build_department_timetable_q(dept_id, prefix=prefix)

    dept_qs = get_user_scope_departments(user)
    fac_qs = get_user_scope_faculties(user)
    sch_qs = get_user_scope_schools(user)
    base_q = (
        Q(**{f"{p}course__owning_department__in": dept_qs})
        | Q(**{f"{p}course__owning_faculty__in": fac_qs})
        | Q(**{f"{p}course__owning_school__in": sch_qs})
        | Q(venue__owning_department__in=dept_qs)
        | Q(venue__owning_faculty__in=fac_qs)
        | Q(venue__owning_school__in=sch_qs)
        | Q(**{f"{p}course__access_grants__granted_to_department__in": dept_qs, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__target_program__department__in": dept_qs, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__granted_to_faculty__in": fac_qs, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__granted_to_school__in": sch_qs, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__owning_level": "general"})
        | Q(**{f"{p}entry_type": "event"})
    )
    if p:
        base_q |= (
            Q(**{f"{p}venue__owning_department__in": dept_qs})
            | Q(**{f"{p}venue__owning_faculty__in": fac_qs})
            | Q(**{f"{p}venue__owning_school__in": sch_qs})
        )
    return base_q


def build_department_timetable_q(department_id, prefix=""):
    """
    Constructs a Q filter for a department timetable view.
    Includes:
    - Events
    - Courses owned directly by this department
    - Courses targeting a program under this department
    - Leased courses with approved access grants to this department (or any of its programs)
    - Leased courses granted to its parent faculty or school
    - Faculty-foundation courses owned by its parent faculty
    - School-level foundation courses
    - University-wide general courses and GST courses
    """
    p = prefix
    dept = Department.objects.filter(id=department_id).select_related("faculty").first()
    fac_id = dept.faculty_id if dept else None
    sch_id = dept.faculty.school_id if (dept and dept.faculty) else None

    q = (
        Q(**{f"{p}entry_type": "event"})
        | Q(**{f"{p}course__owning_department_id": department_id})
        | Q(**{f"{p}course__target_program__department_id": department_id})
        | Q(**{f"{p}course__access_grants__granted_to_department_id": department_id, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__target_program__department_id": department_id, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__owning_level": "general"})
    )
    if fac_id:
        q |= (
            Q(**{f"{p}course__access_grants__granted_to_faculty_id": fac_id, f"{p}course__access_grants__status": "approved"})
            | (Q(**{f"{p}course__owning_level": "faculty"}) & Q(**{f"{p}course__owning_faculty_id": fac_id}))
        )
    if sch_id:
        q |= (
            Q(**{f"{p}course__access_grants__granted_to_school_id": sch_id, f"{p}course__access_grants__status": "approved"})
            | (Q(**{f"{p}course__owning_level": "school"}) & Q(**{f"{p}course__owning_school_id": sch_id}))
        )
    return q


def build_faculty_timetable_q(faculty_id, prefix=""):
    """
    Constructs a Q filter for a faculty timetable view.
    Includes:
    - Events
    - Courses owned directly by this faculty
    - Courses owned by any department within this faculty
    - Leased courses granted to this faculty or any department within it
    - School-level foundation courses
    - University-wide general courses and GST courses
    """
    p = prefix
    fac = Faculty.objects.filter(id=faculty_id).first()
    sch_id = fac.school_id if fac else None

    q = (
        Q(**{f"{p}entry_type": "event"})
        | Q(**{f"{p}course__owning_faculty_id": faculty_id})
        | Q(**{f"{p}course__owning_department__faculty_id": faculty_id})
        | Q(**{f"{p}course__access_grants__granted_to_faculty_id": faculty_id, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__granted_to_department__faculty_id": faculty_id, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__access_grants__target_program__department__faculty_id": faculty_id, f"{p}course__access_grants__status": "approved"})
        | Q(**{f"{p}course__owning_level": "general"})
    )
    if sch_id:
        q |= (
            Q(**{f"{p}course__access_grants__granted_to_school_id": sch_id, f"{p}course__access_grants__status": "approved"})
            | (Q(**{f"{p}course__owning_level": "school"}) & Q(**{f"{p}course__owning_school_id": sch_id}))
        )
    return q


def build_program_timetable_q(program_id, prefix=""):
    """
    Constructs a Q filter for a program timetable view.
    Includes:
    - Events
    - Courses targeting this specific program
    - Leased courses granted specifically to this program
    - Courses owned by this program's department (department-general or targeting this program)
    - Leased courses granted to this program's department (department-general or targeting this program)
    - Leased courses granted to its faculty or school
    - Faculty-foundation courses owned by its faculty
    - School-level foundation courses
    - University-wide general courses and GST courses
    """
    p = prefix
    prog = Program.objects.filter(id=program_id).select_related("department__faculty").first()
    if not prog:
        return (
            Q(**{f"{p}entry_type": "event"})
            | Q(**{f"{p}course__target_program_id": program_id})
            | Q(**{f"{p}course__owning_level__in": ["faculty", "school", "general"]})
            | Q(**{f"{p}course__code__startswith": "GST"})
        )

    dept_id = prog.department_id
    fac_id = prog.department.faculty_id if prog.department else None
    sch_id = prog.department.faculty.school_id if (prog.department and prog.department.faculty) else None

    q = (
        Q(**{f"{p}entry_type": "event"})
        | Q(**{f"{p}course__target_program_id": program_id})
        | Q(**{f"{p}course__access_grants__target_program_id": program_id, f"{p}course__access_grants__status": "approved"})
        | (
            Q(**{f"{p}course__owning_department_id": dept_id})
            & (Q(**{f"{p}course__target_program_id__isnull": True}) | Q(**{f"{p}course__target_program_id": program_id}))
        )
        | (
            Q(**{f"{p}course__access_grants__granted_to_department_id": dept_id, f"{p}course__access_grants__status": "approved"})
            & (Q(**{f"{p}course__access_grants__target_program_id__isnull": True}) | Q(**{f"{p}course__access_grants__target_program_id": program_id}))
        )
        | Q(**{f"{p}course__owning_level": "general"})
    )
    if fac_id:
        q |= (
            Q(**{f"{p}course__access_grants__granted_to_faculty_id": fac_id, f"{p}course__access_grants__status": "approved"})
            | (Q(**{f"{p}course__owning_level": "faculty"}) & Q(**{f"{p}course__owning_faculty_id": fac_id}))
        )
    if sch_id:
        q |= (
            Q(**{f"{p}course__access_grants__granted_to_school_id": sch_id, f"{p}course__access_grants__status": "approved"})
            | (Q(**{f"{p}course__owning_level": "school"}) & Q(**{f"{p}course__owning_school_id": sch_id}))
        )
    return q
