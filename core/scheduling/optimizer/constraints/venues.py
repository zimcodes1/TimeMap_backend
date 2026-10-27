from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def check_venue_conflicts(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates venue double-bookings within the current generation's chromosome.
    A conflict occurs when two distinct course occurrences are assigned to the exact
    same venue during the exact same time slot.
    Returns:
      (conflict_count, conflict_details_list)
    """
    conflicts: List[Dict[str, Any]] = []
    conflict_count = 0

    # Key: (slot_id, venue_id)
    slot_venue_map: Dict[Tuple[str, int | str], List[Assignment]] = {}
    for a in assignments:
        key = (a.slot.slot_id, a.venue_id)
        slot_venue_map.setdefault(key, []).append(a)

    for (slot_id, venue_id), booked_list in slot_venue_map.items():
        if len(booked_list) > 1:
            for i in range(len(booked_list) - 1):
                a1 = booked_list[i]
                a2 = booked_list[i + 1]
                conflict_count += 1
                venue = problem.venues.get(venue_id)
                venue_name = venue.name if venue else f"Venue #{venue_id}"

                conflicts.append(
                    {
                        "type": "venue_conflict",
                        "venue_id": str(venue_id),
                        "venue_name": venue_name,
                        "course_a": a1.course_code,
                        "course_b": a2.course_code,
                        "occurrence_a": a1.occurrence.occurrence_id,
                        "occurrence_b": a2.occurrence.occurrence_id,
                        "slot": str(a1.slot),
                    }
                )

    return conflict_count, conflicts


def check_pre_existing_conflicts(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Detects assignments that collide with slots already occupied by ancestor or peer
    published timetables (venues, lecturers, or student cohorts).

    This is treated as a HARD constraint: any such placement is a direct conflict
    with an existing, live lecture and must be penalised heavily.

    Returns:
      (conflict_count, conflict_details_list)
    """
    has_venues = bool(problem.blocked_venue_slots)
    has_lecturers = bool(getattr(problem, "blocked_lecturer_slots", None))
    has_cohorts = bool(getattr(problem, "blocked_cohort_slots", None))

    if not (has_venues or has_lecturers or has_cohorts):
        return 0, []

    conflicts: List[Dict[str, Any]] = []
    conflict_count = 0

    for a in assignments:
        sid = a.slot.slot_id

        # 1. Venue pre-existing clash
        if has_venues:
            blocked = problem.blocked_venue_slots.get(a.venue_id)
            if blocked and sid in blocked:
                conflict_count += 1
                venue = problem.venues.get(a.venue_id)
                venue_name = venue.name if venue else f"Venue #{a.venue_id}"
                conflicts.append(
                    {
                        "type": "pre_existing_conflict",
                        "sub_type": "venue",
                        "venue_id": str(a.venue_id),
                        "venue_name": venue_name,
                        "course": a.course_code,
                        "occurrence": a.occurrence.occurrence_id,
                        "slot": str(a.slot),
                        "detail": (
                            f"Venue '{venue_name}' is already occupied in a published timetable during {a.slot}."
                        ),
                    }
                )

        # 2. Lecturer pre-existing clash
        if has_lecturers:
            for lid in a.occurrence.lecturer_ids:
                blocked = problem.blocked_lecturer_slots.get(lid)
                if blocked and sid in blocked:
                    conflict_count += 1
                    lec_info = problem.lecturer_details.get(lid)
                    lec_name = lec_info.name if lec_info else f"Staff #{lid}"
                    conflicts.append(
                        {
                            "type": "pre_existing_conflict",
                            "sub_type": "lecturer",
                            "lecturer_id": str(lid),
                            "lecturer_name": lec_name,
                            "course": a.course_code,
                            "occurrence": a.occurrence.occurrence_id,
                            "slot": str(a.slot),
                            "detail": (
                                f"Lecturer {lec_name} is already committed to another lecture during {a.slot} in a published timetable."
                            ),
                        }
                    )

        # 3. Student cohort pre-existing clash
        if has_cohorts:
            for grp in a.occurrence.student_groups:
                cohort_key = (grp.program_id, grp.level)
                blocked = problem.blocked_cohort_slots.get(cohort_key)
                if blocked and sid in blocked:
                    conflict_count += 1
                    conflicts.append(
                        {
                            "type": "pre_existing_conflict",
                            "sub_type": "student_cohort",
                            "program_id": grp.program_id,
                            "program_name": grp.display_name,
                            "level": grp.level,
                            "course": a.course_code,
                            "occurrence": a.occurrence.occurrence_id,
                            "slot": str(a.slot),
                            "detail": (
                                f"Cohort {grp.display_name} {grp.level}L is already scheduled for another course during {a.slot} in a published timetable."
                            ),
                        }
                    )

    return conflict_count, conflicts
