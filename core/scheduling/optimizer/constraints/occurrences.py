from collections import defaultdict
from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def check_occurrence_days(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates multi-occurrence day separation.
    Occurrences of the same course must be scheduled on distinct days
    (e.g., MTH101 on Monday and Wednesday, not Monday and Monday).
    Returns:
      (violation_count, violation_details_list)
    """
    violations: List[Dict[str, Any]] = []
    total_violations = 0

    # Group assignments by course_id
    course_assignments: Dict[int | str, List[Assignment]] = defaultdict(list)
    for a in assignments:
        course_assignments[a.course_id].append(a)

    day_names = {
        "MO": "Monday",
        "TU": "Tuesday",
        "WE": "Wednesday",
        "TH": "Thursday",
        "FR": "Friday",
    }

    for cid, a_list in course_assignments.items():
        if len(a_list) < 2:
            continue

        # Count occurrences per day
        day_map: Dict[str, List[Assignment]] = defaultdict(list)
        for a in a_list:
            day_map[a.slot.day].append(a)

        for day, same_day_list in day_map.items():
            if len(same_day_list) > 1:
                overflow = len(same_day_list) - 1
                total_violations += overflow
                course_code = same_day_list[0].course_code

                violations.append(
                    {
                        "type": "occurrence_day_violation",
                        "course": course_code,
                        "day": day_names.get(day, day),
                        "same_day_count": len(same_day_list),
                        "occurrences": [a.occurrence.occurrence_id for a in same_day_list],
                    }
                )

    return total_violations, violations

