"""Deterministic conflict repair pipeline for examination schedules."""

from datetime import date, time
from typing import Any, Dict, List, Tuple

from ..models.problem import ExamSchedulingProblem
from ..preprocessing.calendar import date_windows, is_within_policy


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def repair_conflicts(
    events: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
    problem: ExamSchedulingProblem,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Scans for student clashes or venue collisions and attempts deterministic resolution.

    Iterates through colliding pairs, unseats the later-indexed event, and searches for
    the earliest valid conflict-free alternate window.
    """
    for index in range(len(events)):
        first = events[index]
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
            conflict_graph = problem.student_conflict_graph or {}
            is_joined = (
                first.get("joined_session_id")
                and first.get("joined_session_id") == second.get("joined_session_id")
            )
            stu_clash = bool(
                first_state["student_ids"].intersection(second_state["student_ids"])
            ) or (second["course_id"] in conflict_graph.get(first["course_id"], set()))
            ven_clash = bool(
                not is_joined and first_state["venue_ids"].intersection(second_state["venue_ids"])
            )

            if stu_clash or ven_clash:
                # Attempt to move the second event to an alternate window
                duration = second["duration_minutes"]
                for alt_day, alt_start in date_windows(
                    problem.start_date, problem.end_date, problem.policy
                ):
                    if not is_within_policy(alt_day, alt_start, duration, problem.policy):
                        continue

                    finish_m = _minutes(alt_start) + duration
                    finish = time(finish_m // 60, finish_m % 60)

                    has_clash = False
                    for other_idx, other_state in enumerate(scheduled_states):
                        if other_idx == second_index:
                            continue
                        if other_state["date"] != alt_day.isoformat():
                            continue

                        other_start = time.fromisoformat(other_state["start_time"])
                        other_end = time.fromisoformat(other_state["end_time"])
                        if alt_start < other_end and other_start < finish:
                            if second_state["student_ids"].intersection(
                                other_state["student_ids"]
                            ) or second_state["venue_ids"].intersection(
                                other_state["venue_ids"]
                            ):
                                has_clash = True
                                break

                    if not has_clash and getattr(problem, "blocked_venue_windows", None):
                        for vid in second_state["venue_ids"]:
                            for ext in problem.blocked_venue_windows.get(vid, []):
                                if ext["date"] == alt_day:
                                    if alt_start < ext["end_time"] and ext["start_time"] < finish:
                                        has_clash = True
                                        break
                            if has_clash:
                                break

                    if not has_clash and getattr(problem, "blocked_student_windows", None):
                        for stu_id in second_state["student_ids"]:
                            for ext in problem.blocked_student_windows.get(stu_id, []):
                                if ext["date"] == alt_day:
                                    if alt_start < ext["end_time"] and ext["start_time"] < finish:
                                        has_clash = True
                                        break
                            if has_clash:
                                break

                    if not has_clash:
                        # Apply repair
                        second["date"] = alt_day.isoformat()
                        second["start_time"] = alt_start.isoformat()
                        second["end_time"] = finish.isoformat()
                        second["explanation"] = (
                            "Repaired into conflict-free window by deterministic repair pass."
                        )
                        second_state["date"] = alt_day.isoformat()
                        second_state["start_time"] = alt_start.isoformat()
                        second_state["end_time"] = finish.isoformat()
                        break

    return events, scheduled_states

