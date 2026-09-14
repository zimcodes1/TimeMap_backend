from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def check_lecturer_conflicts(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates lecturer double-booking.
    A conflict occurs when a lecturer is scheduled to teach two distinct course occurrences
    in the same time slot.
    Returns:
      (conflict_count, conflict_details_list)
    """
    conflicts: List[Dict[str, Any]] = []
    conflict_count = 0

    # Group by slot
    slot_assignments: Dict[str, List[Assignment]] = {}
    for a in assignments:
        slot_assignments.setdefault(a.slot.slot_id, []).append(a)

    for slot_id, slot_group in slot_assignments.items():
        if len(slot_group) < 2:
            continue

        # Map each lecturer to assignments in this slot
        lecturer_slots: Dict[int | str, List[Assignment]] = {}
        for a in slot_group:
            for lid in a.occurrence.lecturer_ids:
                lecturer_slots.setdefault(lid, []).append(a)

        for lid, assigned_list in lecturer_slots.items():
            if len(assigned_list) > 1:
                # Double booking!
                for k in range(len(assigned_list) - 1):
                    a1 = assigned_list[k]
                    a2 = assigned_list[k + 1]
                    conflict_count += 1
                    lecturer_info = problem.lecturer_details.get(lid)
                    lecturer_name = lecturer_info.name if lecturer_info else f"Lecturer #{lid}"

                    conflicts.append(
                        {
                            "type": "lecturer_conflict",
                            "lecturer_id": str(lid),
                            "lecturer_name": lecturer_name,
                            "course_a": a1.course_code,
                            "course_b": a2.course_code,
                            "occurrence_a": a1.occurrence.occurrence_id,
                            "occurrence_b": a2.occurrence.occurrence_id,
                            "slot": str(a1.slot),
                        }
                    )

    return conflict_count, conflicts

