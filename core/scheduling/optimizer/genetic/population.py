import random
from collections import defaultdict
from typing import Dict, List, Set

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome


def create_random_individual(problem: SchedulingProblem) -> Chromosome:
    """
    Creates a random chromosome: each occurrence is assigned a random valid slot
    and a randomly chosen allowed venue.
    """
    genes: List[Assignment] = []
    for occ in problem.occurrences:
        slot = random.choice(problem.valid_slots)
        allowed_venues = problem.allowed_venues_by_course.get(occ.course_id, [])
        if not allowed_venues:
            allowed_venues = list(problem.venues.keys())
        venue_id = random.choice(allowed_venues) if allowed_venues else 0

        genes.append(Assignment(occurrence=occ, slot=slot, venue_id=venue_id))

    return Chromosome(genes)


def create_heuristic_individual(problem: SchedulingProblem) -> Chromosome:
    """
    Creates a chromosome with smart heuristic placement:
      1. For repeated occurrences of the same course, assigns them to distinct days.
      2. Avoids placing multiple occurrences for the same student cohort in the same slot.
      3. Prefers venues that match or exceed expected student capacity.
      4. Spreads lectures across the days of the week to stay within daily limits.
    """
    genes: List[Assignment] = []

    # Track usage per course: course_id -> set of assigned days
    course_assigned_days: Dict[int | str, Set[str]] = defaultdict(set)
    # Track occupied slots per student group: (group_id, slot_id) -> bool
    group_occupied_slots: Set[str] = set()

    # Shuffle occurrences order so different individuals explore different placements
    indexed_occurrences = list(enumerate(problem.occurrences))
    random.shuffle(indexed_occurrences)

    # Pre-allocate genes list with placeholders
    placed_genes: List[Assignment | None] = [None] * len(problem.occurrences)

    for original_idx, occ in indexed_occurrences:
        cid = occ.course_id
        used_days = course_assigned_days[cid]

        # 1. Filter candidate slots: prefer days not yet used by this course
        candidate_slots = [s for s in problem.valid_slots if s.day not in used_days]
        if not candidate_slots:
            candidate_slots = list(problem.valid_slots)

        # 2. Prefer slots where this cohort is not yet scheduled
        conflict_free_slots = []
        for s in candidate_slots:
            has_conflict = False
            for grp in occ.student_groups:
                key = f"{grp.group_id}_{s.slot_id}"
                if key in group_occupied_slots:
                    has_conflict = True
                    break
            if not has_conflict:
                conflict_free_slots.append(s)

        chosen_slot = (
            random.choice(conflict_free_slots)
            if conflict_free_slots
            else random.choice(candidate_slots)
        )

        # Record assigned day and cohort slots
        course_assigned_days[cid].add(chosen_slot.day)
        for grp in occ.student_groups:
            group_occupied_slots.add(f"{grp.group_id}_{chosen_slot.slot_id}")

        # 3. Choose venue: prefer allowed venues with sufficient capacity
        allowed_venue_ids = problem.allowed_venues_by_course.get(cid, [])
        if not allowed_venue_ids:
            allowed_venue_ids = list(problem.venues.keys())

        fitting_venues = []
        for vid in allowed_venue_ids:
            v = problem.venues.get(vid)
            if v and v.capacity >= occ.expected_students:
                fitting_venues.append(vid)

        chosen_venue_id = (
            random.choice(fitting_venues)
            if fitting_venues
            else (random.choice(allowed_venue_ids) if allowed_venue_ids else 0)
        )

        placed_genes[original_idx] = Assignment(
            occurrence=occ,
            slot=chosen_slot,
            venue_id=chosen_venue_id,
        )

    # Cast list to non-optional
    return Chromosome([g for g in placed_genes if g is not None])


def create_initial_population(
    problem: SchedulingProblem,
    population_size: int,
    heuristic_ratio: float = 0.8,
) -> List[Chromosome]:
    """
    Generates initial population combining smart heuristic individuals
    with randomized individuals to balance quality and genetic diversity.
    """
    population: List[Chromosome] = []
    heuristic_count = int(population_size * heuristic_ratio)

    for _ in range(heuristic_count):
        population.append(create_heuristic_individual(problem))

    for _ in range(population_size - heuristic_count):
        population.append(create_random_individual(problem))

    return population

