import random
from collections import defaultdict
from typing import Dict, List, Set

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome


def repair_chromosome(
    chromosome: Chromosome,
    problem: SchedulingProblem,
) -> Chromosome:
    """
    Post-crossover/mutation repair operator:
      1. Resolves duplicate day placements for multi-occurrence courses.
      2. Ensures assigned venues are strictly members of allowed_venues_by_course.
    """
    assignments = list(chromosome.assignments)
    repaired = False

    # 1. Check multi-occurrence courses for same-day duplicates
    course_indices: Dict[int | str, List[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        course_indices[a.course_id].append(i)

    for cid, indices in course_indices.items():
        if len(indices) < 2:
            continue

        assigned_days: Set[str] = set()
        for idx in indices:
            a = assignments[idx]
            if a.slot.day in assigned_days:
                # Duplicate day: find a slot on an unused day
                all_days = {"MO", "TU", "WE", "TH", "FR"}
                unused_days = list(all_days - assigned_days)
                if unused_days:
                    target_day = random.choice(unused_days)
                    alt_slots = [s for s in problem.valid_slots if s.day == target_day]
                    if alt_slots:
                        new_slot = random.choice(alt_slots)
                        assignments[idx] = Assignment(
                            occurrence=a.occurrence,
                            slot=new_slot,
                            venue_id=a.venue_id,
                        )
                        assigned_days.add(target_day)
                        repaired = True
                        continue

            assigned_days.add(a.slot.day)

    # 2. Check allowed venues validity
    for i, a in enumerate(assignments):
        cid = a.course_id
        allowed = problem.allowed_venues_by_course.get(cid, [])
        if allowed and a.venue_id not in allowed:
            assignments[i] = Assignment(
                occurrence=a.occurrence,
                slot=a.slot,
                venue_id=random.choice(allowed),
            )
            repaired = True

    return Chromosome(assignments) if repaired else chromosome

