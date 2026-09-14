from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def check_venue_conflicts(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates venue double-bookings.
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

