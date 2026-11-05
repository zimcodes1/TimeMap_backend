"""Student workload evaluation: weekly load, daily load, and distribution penalties."""

from datetime import date
from typing import Any, Dict, List, Tuple


def calculate_student_workload(
    scheduled_states: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes student examination distribution metrics across days and weeks."""
    weekly_loads: Dict[Tuple[int | str, Tuple[int, int]], int] = {}
    daily_loads: Dict[Tuple[int | str, str], int] = {}

    for state in scheduled_states:
        exam_day = date.fromisoformat(state["date"])
        iso = exam_day.isocalendar()
        week_key = (iso.year, iso.week)

        for student_id in state["student_ids"]:
            weekly_loads[(student_id, week_key)] = (
                weekly_loads.get((student_id, week_key), 0) + 1
            )
            daily_loads[(student_id, state["date"])] = (
                daily_loads.get((student_id, state["date"]), 0) + 1
            )

    max_weekly = max(weekly_loads.values(), default=0)
    over_three = len({student for (student, _), count in weekly_loads.items() if count > 3})
    avg_weekly = (
        round(sum(weekly_loads.values()) / len(weekly_loads), 2)
        if weekly_loads
        else 0.0
    )
    max_daily = max(daily_loads.values(), default=0)

    return {
        "maximum_exams_per_student_per_week": max_weekly,
        "students_over_three_exams_per_week": over_three,
        "average_exams_per_student_week": avg_weekly,
        "maximum_exams_per_student_per_day": max_daily,
        "weekly_loads": weekly_loads,
        "daily_loads": daily_loads,
    }


def calculate_workload_penalty(workload_stats: Dict[str, Any]) -> float:
    """Calculates a soft objective penalty for uneven student examination distribution."""
    weekly_loads = workload_stats.get("weekly_loads", {})
    daily_loads = workload_stats.get("daily_loads", {})

    penalty = 0.0
    for count in weekly_loads.values():
        if count > 3:
            penalty += (count - 3) * 50.0

    for count in daily_loads.values():
        if count > 1:
            penalty += (count - 1) * 30.0

    return penalty

