"""Constructive search algorithm for examination scheduling."""

from datetime import date, time
from typing import Any, Dict, List, Set, Tuple

from ..allocation.planner import allocate_venues
from ..models.problem import ExamSchedulingProblem
from ..preprocessing.calendar import date_windows, is_within_policy
from .ordering import order_exam_events


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def search_exam_schedule(
    problem: ExamSchedulingProblem,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    int,
]:
    """Constructs a conflict-free examination schedule using heuristic placement and physical venue allocation.

    Returns:
        (events, scheduled_states, unscheduled_diagnostics, candidate_windows_evaluated)
    """
    events: List[Dict[str, Any]] = []
    scheduled_states: List[Dict[str, Any]] = []
    unscheduled: List[Dict[str, Any]] = []
    candidate_windows_evaluated = 0

    ordered = order_exam_events(list(problem.events.values()))

    for event_data in ordered:
        students = event_data.student_ids
        count = event_data.student_count
        exam_type = event_data.exam_type
        duration = event_data.duration_minutes
        per_student = event_data.duration_per_student_minutes

        eligible_venues = problem.venues_by_type.get(exam_type, [])
        allocation = allocate_venues(
            eligible_venues, count, exam_type, duration, per_student
        )

        if not allocation:
            unscheduled.append(
                {
                    "course_id": event_data.course_id,
                    "course_code": event_data.course_code,
                    "reason": "No compatible venue configuration can accommodate this population.",
                }
            )
            continue

        actual_duration, venue_allocs = allocation
        venue_ids = {a["venue_id"] for a in venue_allocs}

        candidates = []
        for day, start_time in date_windows(
            problem.start_date, problem.end_date, problem.policy
        ):
            candidate_windows_evaluated += 1

            if not is_within_policy(day, start_time, actual_duration, problem.policy):
                continue

            finish_minutes = _minutes(start_time) + actual_duration
            finish = time(finish_minutes // 60, finish_minutes % 60)

            overlaps = False
            weekly_loads = []
            daily_loads = []

            for old in scheduled_states:
                old_date = date.fromisoformat(old["date"])
                old_start = time.fromisoformat(old["start_time"])
                old_end = time.fromisoformat(old["end_time"])

                # Check student workload distribution
                if students and students.intersection(old["student_ids"]):
                    if (
                        old_date.isocalendar().week == day.isocalendar().week
                        and old_date.isocalendar().year == day.isocalendar().year
                    ):
                        weekly_loads.append(old)
                    if old["date"] == day.isoformat():
                        daily_loads.append(old)

                # Check temporal clash on the same calendar day
                if old["date"] != day.isoformat():
                    continue

                if not (start_time < old_end and old_start < finish):
                    continue

                # Hard clash if sharing students or sharing any venue
                if (students and students.intersection(old["student_ids"])) or venue_ids.intersection(
                    old["venue_ids"]
                ):
                    overlaps = True
                    break

            if not overlaps:
                # Rank by: (fewest exams this week, fewest exams this day, earlier calendar date, earlier time)
                score_key = (len(weekly_loads), len(daily_loads), day, start_time)
                candidates.append((score_key, (day, start_time, finish)))

        if not candidates:
            unscheduled.append(
                {
                    "course_id": event_data.course_id,
                    "course_code": event_data.course_code,
                    "reason": "No conflict-free time window within the configured exam period.",
                }
            )
            continue

        chosen = min(candidates, key=lambda c: c[0])[1]
        day, start_time, finish = chosen

        event_payload = {
            "course_id": event_data.course_id,
            "course_code": event_data.course_code,
            "course_title": event_data.course_title,
            "course_level": event_data.course_level,
            "department_id": event_data.department_id,
            "department_name": event_data.department_name,
            "program_id": event_data.program_id,
            "program_name": event_data.program_name,
            "exam_type": exam_type,
            "student_count": count,
            "date": day.isoformat(),
            "start_time": start_time.isoformat(),
            "end_time": finish.isoformat(),
            "duration_minutes": actual_duration,
            "venues": venue_allocs,
            "joined_courses": [],
            "explanation": "Scheduled by student-conflict, operating-window, and venue-capacity checks.",
        }

        events.append(event_payload)
        scheduled_states.append(
            {
                "date": day.isoformat(),
                "start_time": event_payload["start_time"],
                "end_time": event_payload["end_time"],
                "student_ids": students,
                "venue_ids": venue_ids,
            }
        )

    return events, scheduled_states, unscheduled, candidate_windows_evaluated

