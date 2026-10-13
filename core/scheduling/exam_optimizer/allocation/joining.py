"""Session joining logic for small compatible examinations."""

from typing import Any, Dict, List, Set
from courses.models import Course


MAX_COURSES_PER_JOINED_SESSION = 2
MAX_CBT_JOIN_STUDENTS = 100
MAX_WRITTEN_JOIN_STUDENTS = 60


def join_compatible_sessions(
    events: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
) -> int:
    """Identifies and groups small compatible simultaneous examinations into shared sessions.

    Hard Invariants:
    - At most 2 courses per joined CBT session.
    - Zero student registration overlap.
    - Zero venue collision.
    - Identical date, time window, exam type, and duration.

    Modifies events in-place with `joined_courses` and `joined_session_id`.
    Returns the count of joined session pairs formed.
    """
    grouped_indices: Set[int] = set()

    for index, event in enumerate(events):
        if index in grouped_indices:
            continue

        compatible_match: Optional[int] = None
        for other_index in range(index + 1, len(events)):
            if other_index in grouped_indices:
                continue

            other = events[other_index]

            # 1. Matching temporal and type signature
            signature_a = (
                event["date"],
                event["start_time"],
                event["end_time"],
                event["exam_type"],
                event["duration_minutes"],
            )
            signature_b = (
                other["date"],
                other["start_time"],
                other["end_time"],
                other["exam_type"],
                other["duration_minutes"],
            )
            if signature_a != signature_b:
                continue

            # 2. Maximum student cohort threshold for joining
            is_cbt = event["exam_type"] == Course.ExamType.CBT
            limit = MAX_CBT_JOIN_STUDENTS if is_cbt else MAX_WRITTEN_JOIN_STUDENTS
            if event["student_count"] > limit or other["student_count"] > limit:
                continue

            # 3. Constraint checks from scheduled states
            state_a, state_b = scheduled_states[index], scheduled_states[other_index]
            if state_a["student_ids"].intersection(state_b["student_ids"]):
                continue
            if state_a["venue_ids"].intersection(state_b["venue_ids"]):
                continue

            compatible_match = other_index
            break

        if compatible_match is not None:
            other_index = compatible_match
            event["joined_courses"] = [events[other_index]["course_code"]]
            events[other_index]["joined_courses"] = [event["course_code"]]

            session_id = f"{event['date']}:{event['start_time']}:{event['course_id']}"
            event["joined_session_id"] = session_id
            events[other_index]["joined_session_id"] = session_id

            grouped_indices.update({index, other_index})

    return len(grouped_indices) // 2

