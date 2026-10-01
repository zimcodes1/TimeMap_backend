import random
from typing import List

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome
from .venue_utils import pick_best_fit_venue


def mutate(
    chromosome: Chromosome,
    problem: SchedulingProblem,
    mutation_rate: float = 0.08,
) -> Chromosome:
    """
    Mutates genes in the chromosome.
    For each gene with probability mutation_rate:
      - 50% chance: change time slot (same or different day)
      - 25% chance: change venue (from allowed venues with best-fit capacity)
      - 25% chance: full reassignment (new slot and new best-fit venue)
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
                # Slot mutation: pick a new slot
                new_slot = random.choice(problem.valid_slots)
                new_assignments.append(
                    Assignment(occurrence=occ, slot=new_slot, venue_id=assignment.venue_id)
                )
            elif rand_mode < 0.75:
                # Venue mutation: pick a new allowed venue using capacity-aware best-fit
                new_venue_id = (
                    pick_best_fit_venue(
                        expected_students=occ.expected_students,
                        allowed_venue_ids=allowed_venues,
                        venues=problem.venues,
                    )
                    if allowed_venues
                    else assignment.venue_id
                )
                new_assignments.append(
                    Assignment(occurrence=occ, slot=assignment.slot, venue_id=new_venue_id)
                )
            else:
                # Full reassignment: new slot and new best-fit venue
                new_slot = random.choice(problem.valid_slots)
                new_venue_id = (
                    pick_best_fit_venue(
                        expected_students=occ.expected_students,
                        allowed_venue_ids=allowed_venues,
                        venues=problem.venues,
                    )
                    if allowed_venues
                    else assignment.venue_id
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
    reassigning them to alternative slots/venues to resolve clashes.
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

    # Try alternative slots and pick randomly
    alt_slots = [s for s in problem.valid_slots if s.slot_id != curr_assignment.slot.slot_id]
    new_slot = random.choice(alt_slots) if alt_slots else curr_assignment.slot
    new_venue_id = (
        pick_best_fit_venue(
            expected_students=occ.expected_students,
            allowed_venue_ids=allowed_venues,
            venues=problem.venues,
        )
        if allowed_venues
        else curr_assignment.venue_id
    )

    cloned[target_idx] = Assignment(occurrence=occ, slot=new_slot, venue_id=new_venue_id)
    return cloned
