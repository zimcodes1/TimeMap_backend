"""Calendar constraint checks for examination schedules."""

from datetime import date, time
from typing import Any, Dict, List

from ..preprocessing.calendar import is_within_policy


def check_calendar_constraints(
    events: List[Dict[str, Any]],
    start_date: date,
    end_date: date,
) -> List[Dict[str, str]]:
    """Validates that all scheduled exam events conform to calendar bounds and daily operating policies.

    Enforces:
    - H1: Exam date is within [exam_start_date, exam_end_date].
    - H10: Operating window 08:00–18:00, Mon–Sat only, Friday 12:00–14:00 Jummat blackout observed.
    """
    errors: List[Dict[str, str]] = []

    for event in events:
        day = date.fromisoformat(event["date"])
        start_time = time.fromisoformat(event["start_time"])
        duration = event["duration_minutes"]

        if not (start_date <= day <= end_date):
            errors.append(
                {
                    "course_code": event["course_code"],
                    "reason": f"Event falls outside the examination period ({day} not in [{start_date}, {end_date}]).",
                }
            )
            continue

        if day.weekday() == 6:  # Sunday
            errors.append(
                {
                    "course_code": event["course_code"],
                    "reason": "Examinations cannot be scheduled on Sundays.",
                }
            )
            continue

        if not is_within_policy(day, start_time, duration):
            errors.append(
                {
                    "course_code": event["course_code"],
                    "reason": "Event falls outside the configured operating calendar.",
                }
            )

    return errors

