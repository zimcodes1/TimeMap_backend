from typing import Any, Dict, List, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem


def check_student_conflicts(
    assignments: List[Assignment],
    problem: SchedulingProblem,
) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Evaluates student group timetable clashes.
    A conflict occurs when two distinct course occurrences that share student groups
    are assigned to the exact same time slot.
    Returns:
      (conflict_count, conflict_details_list)
    """
    conflicts: List[Dict[str, Any]] = []
    conflict_count = 0

    # Group assignments by slot_id for fast comparison
    slot_assignments: Dict[str, List[Assignment]] = {}
    for a in assignments:
        slot_assignments.setdefault(a.slot.slot_id, []).append(a)

    for slot_id, slot_group in slot_assignments.items():
        if len(slot_group) < 2:
            continue

        n = len(slot_group)
        for i in range(n):
            a1 = slot_group[i]
            cid1 = a1.course_id
            conflicting_courses = problem.student_conflict_graph.get(cid1)
            if not conflicting_courses:
                continue

            for j in range(i + 1, n):
                a2 = slot_group[j]
                cid2 = a2.course_id

                if cid2 in conflicting_courses:
                    conflict_count += 1
                    shared = problem.shared_student_groups.get((cid1, cid2), [])
                    shared_names = [g.display_name for g in shared]

                    conflicts.append(
                        {
                            "type": "student_conflict",
                            "course_a": a1.course_code,
                            "course_b": a2.course_code,
                            "occurrence_a": a1.occurrence.occurrence_id,
                            "occurrence_b": a2.occurrence.occurrence_id,
                            "slot": str(a1.slot),
                            "shared_groups": shared_names,
                        }
                    )

    return conflict_count, conflicts

