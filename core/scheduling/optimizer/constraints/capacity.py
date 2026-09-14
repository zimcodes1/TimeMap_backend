from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def calculate_capacity_penalty(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates venue capacity soft constraint.
    If expected students exceed venue capacity, a soft penalty proportional
    to the student overflow is accrued.
    Capacity shortage does NOT make the assignment illegal.
    Returns:
      (total_penalty, overflow_details_list)
    """
    overflows: List[Dict[str, Any]] = []
    total_penalty = 0

    for a in assignments:
        venue = problem.venues.get(a.venue_id)
        if not venue:
            continue

        capacity = venue.capacity
        expected = a.occurrence.expected_students

        if expected > capacity:
            overflow = expected - capacity
            total_penalty += overflow

            overflows.append(
                {
                    "type": "capacity_overflow",
                    "course": a.course_code,
                    "occurrence": a.occurrence.occurrence_id,
                    "venue_name": venue.name,
                    "venue_capacity": capacity,
                    "expected_students": expected,
                    "overflow": overflow,
                    "slot": str(a.slot),
                }
            )

    return total_penalty, overflows

