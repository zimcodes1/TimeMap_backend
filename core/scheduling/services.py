import datetime
from django.db import transaction
from .models import LectureSession, TimetableEntry


WEEKDAY_MAP = {
    "monday": 0, "mon": 0, "0": 0,
    "tuesday": 1, "tue": 1, "1": 1,
    "wednesday": 2, "wed": 2, "2": 2,
    "thursday": 3, "thu": 3, "3": 3,
    "friday": 4, "fri": 4, "4": 4,
    "saturday": 5, "sat": 5, "5": 5,
    "sunday": 6, "sun": 6, "6": 6,
}


def parse_target_weekdays(rule_str):
    """
    Parses recurrence rule strings like 'weekly:tuesday', 'weekly:mon,wed,fri', or 'tuesday'
    Returns a set of integer weekdays (0=Monday .. 6=Sunday).
    """
    if not rule_str:
        return set()

    rule_clean = rule_str.strip().lower()
    if ":" in rule_clean:
        _, day_part = rule_clean.split(":", 1)
    else:
        day_part = rule_clean

    tokens = [t.strip() for t in day_part.replace("on", "").replace("every", "").split(",")]
    target_days = set()
    for token in tokens:
        for key, val in WEEKDAY_MAP.items():
            if key in token:
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
