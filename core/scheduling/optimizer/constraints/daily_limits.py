from collections import defaultdict
from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from ..models.student_group import StudentGroup


def check_daily_limits(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates daily student cohort lecture limits.
    A Program + Level cohort should not have more than daily_lecture_limit (default 3)
    lectures scheduled on any single day.
    Returns:
      (violation_count, violation_details_list)
    """
    violations: List[Dict[str, Any]] = []
    total_violations = 0
    max_limit = problem.daily_lecture_limit

    # Count lectures per (StudentGroup, day)
    group_day_counts: Dict[Tuple[StudentGroup, str], int] = defaultdict(int)
    group_day_courses: Dict[Tuple[StudentGroup, str], List[str]] = defaultdict(list)

    for a in assignments:
        day = a.slot.day
        for group in a.occurrence.student_groups:
            key = (group, day)
            group_day_counts[key] += 1
            group_day_courses[key].append(a.course_code)

    for (group, day), count in group_day_counts.items():
        if count > max_limit:
            overflow = count - max_limit
            total_violations += overflow

            day_names = {
                "MO": "Monday",
                "TU": "Tuesday",
                "WE": "Wednesday",
                "TH": "Thursday",
                "FR": "Friday",
            }

            violations.append(
                {
                    "type": "daily_limit_violation",
                    "student_group": group.display_name,
                    "day": day_names.get(day, day),
                    "scheduled_count": count,
                    "max_allowed": max_limit,
                    "overflow": overflow,
                    "courses": group_day_courses[(group, day)],
                }
            )

    return total_violations, violations

