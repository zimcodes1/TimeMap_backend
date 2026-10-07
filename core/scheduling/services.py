import datetime
from django.db import transaction
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
