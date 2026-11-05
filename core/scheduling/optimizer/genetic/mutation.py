import random
from typing import List, Optional

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from ..models.slot import Slot
from .chromosome import Chromosome
from .venue_utils import pick_best_fit_venue


def _pick_mutation_slot(
    occ,
    problem: SchedulingProblem,
    exclude_slot_id: Optional[str] = None,
) -> Slot:
    """
    Selects a slot from valid_slots preferring slots where this occurrence's
    student groups, lecturers, and allowed venues are not pre-blocked.
    """
    valid = [s for s in problem.valid_slots if s.slot_id != exclude_slot_id] if exclude_slot_id else list(problem.valid_slots)
    if not valid:
        return problem.valid_slots[0]

    blocked_cohorts = getattr(problem, "blocked_cohort_slots", {}) or {}
    blocked_lecs = getattr(problem, "blocked_lecturer_slots", {}) or {}
    blocked_venues = getattr(problem, "blocked_venue_slots", {}) or {}
    allowed_vids = problem.allowed_venues_by_course.get(occ.course_id, list(problem.venues.keys()))

    unblocked_slots = []
    for s in valid:
        has_cohort_block = any(
            s.slot_id in blocked_cohorts.get((grp.program_id, grp.level), set())
            for grp in occ.student_groups
        )
        if has_cohort_block:
            continue

        has_lec_block = any(
            s.slot_id in blocked_lecs.get(lid, set())
            for lid in occ.lecturer_ids
        )
        if has_lec_block:
            continue

        # Check if at least one allowed venue is unblocked
        has_venue_free = any(
            s.slot_id not in blocked_venues.get(vid, set())
            for vid in allowed_vids
        )
        if has_venue_free:
            unblocked_slots.append(s)

    return random.choice(unblocked_slots) if unblocked_slots else random.choice(valid)


def _pick_mutation_venue(
    expected_students: int,
    allowed_venues: List[int | str],
    slot_id: str,
    problem: SchedulingProblem,
) -> int | str:
    """
    Selects an allowed venue preferring ones not blocked in the target slot.
    """
    if not allowed_venues:
        return 0
    blocked_venues = getattr(problem, "blocked_venue_slots", {}) or {}
    unblocked = [vid for vid in allowed_venues if slot_id not in blocked_venues.get(vid, set())]
    candidates = unblocked if unblocked else allowed_venues
    return pick_best_fit_venue(
        expected_students=expected_students,
        allowed_venue_ids=candidates,
        venues=problem.venues,
    )


def mutate(
    chromosome: Chromosome,
    problem: SchedulingProblem,
    mutation_rate: float = 0.08,
) -> Chromosome:
    """
    Mutates genes in the chromosome.
    For each gene with probability mutation_rate:
      - 50% chance: change time slot (preferring unblocked slots)
      - 25% chance: change venue (preferring unblocked allowed venues)
      - 25% chance: full reassignment (new unblocked slot and venue)
    """
    new_assignments: List[Assignment] = []

    for i in range(len(chromosome)):
        assignment = chromosome[i]

        if random.random() < mutation_rate:
            occ = assignment.occurrence
            allowed_venues = problem.allowed_venues_by_course.get(occ.course_id, [])
            if not allowed_venues:
                allowed_venues = list(problem.venues.keys())

            rand_mode = random.random()
            if rand_mode < 0.5:
                # Slot mutation: pick a new slot preferring unblocked
                new_slot = _pick_mutation_slot(occ, problem)
                new_assignments.append(
                    Assignment(occurrence=occ, slot=new_slot, venue_id=assignment.venue_id)
                )
            elif rand_mode < 0.75:
                # Venue mutation: pick a new allowed venue avoiding blocked slots
                new_venue_id = _pick_mutation_venue(
                    expected_students=occ.expected_students,
                    allowed_venues=allowed_venues,
                    slot_id=assignment.slot.slot_id,
                    problem=problem,
                )
                new_assignments.append(
                    Assignment(occurrence=occ, slot=assignment.slot, venue_id=new_venue_id)
                )
            else:
                # Full reassignment: new unblocked slot and new unblocked venue
                new_slot = _pick_mutation_slot(occ, problem)
                new_venue_id = _pick_mutation_venue(
                    expected_students=occ.expected_students,
                    allowed_venues=allowed_venues,
                    slot_id=new_slot.slot_id,
                    problem=problem,
                )
                new_assignments.append(
                    Assignment(occurrence=occ, slot=new_slot, venue_id=new_venue_id)
                )
        else:
            new_assignments.append(assignment)

    return Chromosome(new_assignments)


def constraint_aware_mutation(
    chromosome: Chromosome,
    problem: SchedulingProblem,
    conflicted_gene_indices: List[int],
) -> Chromosome:
    """
    Targeted mutation: specifically mutates genes known to be involved in conflicts,
    reassigning them to alternative unblocked slots/venues to resolve clashes.
    """
    if not conflicted_gene_indices:
        return mutate(chromosome, problem, mutation_rate=0.08)

    cloned = chromosome.clone()
    target_idx = random.choice(conflicted_gene_indices)
    curr_assignment = cloned[target_idx]
    occ = curr_assignment.occurrence

    allowed_venues = problem.allowed_venues_by_course.get(occ.course_id, [])
    if not allowed_venues:
        allowed_venues = list(problem.venues.keys())

    # Try alternative slots avoiding external blocks
    new_slot = _pick_mutation_slot(occ, problem, exclude_slot_id=curr_assignment.slot.slot_id)
    new_venue_id = _pick_mutation_venue(
        expected_students=occ.expected_students,
        allowed_venues=allowed_venues,
        slot_id=new_slot.slot_id,
        problem=problem,
    )

    cloned[target_idx] = Assignment(occurrence=occ, slot=new_slot, venue_id=new_venue_id)
    return cloned
