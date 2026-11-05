"""Student conflict constraint checks."""

from datetime import time
from typing import Any, Dict, List


def check_student_conflicts(
    events: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Checks for student clashing between overlapping examination windows.

    Enforces H3: Two exams sharing registered students cannot overlap in time.
    """
    errors: List[Dict[str, str]] = []

    for index, first in enumerate(events):
        first_state = scheduled_states[index]
        first_start = time.fromisoformat(first["start_time"])
        first_end = time.fromisoformat(first["end_time"])

        for second_index in range(index + 1, len(events)):
            second = events[second_index]
            if first["date"] != second["date"]:
                continue

            second_start = time.fromisoformat(second["start_time"])
            second_end = time.fromisoformat(second["end_time"])

            overlaps = first_start < second_end and second_start < first_end
            if not overlaps:
                continue

            second_state = scheduled_states[second_index]
            shared_students = first_state["student_ids"].intersection(
                second_state["student_ids"]
            )
            if shared_students:
                errors.append(
                    {
                        "course_code": first["course_code"],
                        "reason": f"Student conflict with {second['course_code']}.",
                    }
                )

    return errors

