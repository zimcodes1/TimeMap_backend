import random
from collections import defaultdict
from typing import Dict, List, Set

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome
from .venue_utils import pick_best_fit_venue


def _slot_is_blocked(slot_id: str, venue_id: int | str, problem: SchedulingProblem) -> bool:
    """
    Returns True if the given (venue, slot) pair is pre-blocked by a higher-scope
    published timetable. This is a hard constraint — the GA must never assign here.
    """
    blocked_slots = problem.blocked_venue_slots.get(venue_id)
    return blocked_slots is not None and slot_id in blocked_slots


def _any_allowed_venue_free(
    slot_id: str,
    allowed_venue_ids: List[int | str],
    occupied_in_slot: Set[int | str],
    problem: SchedulingProblem,
) -> bool:
    """
    Returns True if at least one allowed venue for this slot is both:
      - not occupied by another course in this chromosome, AND
      - not blocked by a higher-scope published timetable.
    """
    for vid in allowed_venue_ids:
        if vid not in occupied_in_slot and not _slot_is_blocked(slot_id, vid, problem):
            return True
    return False


def pick_venue_avoiding_blocked(
    expected_students: int,
    allowed_venue_ids: List[int | str],
    venues: dict,
    slot_id: str,
    problem: SchedulingProblem,
    occupied_venue_ids: Set[int | str] | None = None,
) -> int | str:
    """
    Wraps pick_best_fit_venue but additionally avoids venues that are pre-blocked
    by higher-scope published timetables for the chosen slot.

    Falls back to any non-blocked allowed venue, then to the standard best-fit
    (ignoring block) as a last resort so the chromosome is always complete.
    """
    occupied_venue_ids = occupied_venue_ids or set()

    # 1. Try non-occupied AND non-blocked venues
    preferred = [
        vid for vid in allowed_venue_ids
        if vid not in occupied_venue_ids and not _slot_is_blocked(slot_id, vid, problem)
    ]
    if preferred:
        return pick_best_fit_venue(
            expected_students=expected_students,
            allowed_venue_ids=preferred,
            venues=venues,
        )

    # 2. Fall back to non-blocked venues (even if occupied by another course in this chromosome)
    non_blocked = [
        vid for vid in allowed_venue_ids
        if not _slot_is_blocked(slot_id, vid, problem)
    ]
    if non_blocked:
        return pick_best_fit_venue(
            expected_students=expected_students,
            allowed_venue_ids=non_blocked,
            venues=venues,
        )

    # 3. Last resort: ignore blocking (will generate a hard conflict — fitness will penalise it)
    return pick_best_fit_venue(
        expected_students=expected_students,
        allowed_venue_ids=allowed_venue_ids,
        venues=venues,
        occupied_venue_ids=occupied_venue_ids,
    )


def create_random_individual(problem: SchedulingProblem) -> Chromosome:
    """
    Creates a random chromosome: each occurrence is assigned a random valid slot
    and a capacity-aware allowed venue.

    Respects higher-scope blocked venue-slots by preferring unblocked slots.
    """
    genes: List[Assignment] = []
    for occ in problem.occurrences:
        allowed_venues = problem.allowed_venues_by_course.get(occ.course_id, [])
        if not allowed_venues:
            allowed_venues = list(problem.venues.keys())

        # Prefer slots where at least one allowed venue is not pre-blocked
        unblocked_slots = [
            s for s in problem.valid_slots
            if any(
                not _slot_is_blocked(s.slot_id, vid, problem)
                for vid in allowed_venues
            )
        ]
        candidate_slots = unblocked_slots if unblocked_slots else list(problem.valid_slots)
        slot = random.choice(candidate_slots)

        venue_id = pick_venue_avoiding_blocked(
            expected_students=occ.expected_students,
            allowed_venue_ids=allowed_venues,
            venues=problem.venues,
            slot_id=slot.slot_id,
            problem=problem,
        )

        genes.append(Assignment(occurrence=occ, slot=slot, venue_id=venue_id))

    return Chromosome(genes)


def create_heuristic_individual(problem: SchedulingProblem) -> Chromosome:
    """
    Creates a chromosome with smart heuristic placement:
      1. Prioritizes larger student cohorts first so they secure adequately-sized halls.
      2. For repeated occurrences of the same course, assigns them to distinct days.
      3. Avoids placing multiple occurrences for the same student cohort in the same slot.
      4. Avoids double-booking lecturers across concurrent occurrences.
      5. Tracks slot venue occupancy to avoid venue clashes and uses best-fit capacity sizing.
      6. Spreads lectures across the days of the week to stay within daily limits.
      7. Respects higher-scope blocked venue-slots as hard constraints.
    """
    # Track usage per course: course_id -> set of assigned days
    course_assigned_days: Dict[int | str, Set[str]] = defaultdict(set)
    # Track occupied slots per student group: (group_id, slot_id) -> bool
    group_occupied_slots: Set[str] = set()
    # Track occupied slots per lecturer: (lecturer_id, slot_id) -> bool
    lecturer_occupied_slots: Set[str] = set()
    # Track occupied venues per slot: slot_id -> set of venue_ids
    slot_venue_occupancy: Dict[str, Set[int | str]] = defaultdict(set)

    # Order occurrences with large cohorts prioritized first, with random jitter for diversity
    indexed_occurrences = list(enumerate(problem.occurrences))
    indexed_occurrences.sort(
        key=lambda item: item[1].expected_students + random.randint(-15, 15),
        reverse=True,
    )

    # Pre-allocate genes list with placeholders to preserve 1-to-1 index alignment
    placed_genes: List[Assignment | None] = [None] * len(problem.occurrences)

    for original_idx, occ in indexed_occurrences:
        cid = occ.course_id
        used_days = course_assigned_days[cid]

        # 1. Filter candidate slots: prefer days not yet used by this course
        candidate_slots = [s for s in problem.valid_slots if s.day not in used_days]
        if not candidate_slots:
            candidate_slots = list(problem.valid_slots)

        allowed_venue_ids = problem.allowed_venues_by_course.get(cid, [])
        if not allowed_venue_ids:
            allowed_venue_ids = list(problem.venues.keys())

        # 2. Prefer slots where:
        #    a) No student group is in conflict
        #    b) No lecturer is in conflict
        #    c) At least one allowed venue is free (not occupied AND not pre-blocked)
        ideal_slots = []
        cohort_and_lec_free_slots = []
        cohort_free_slots = []

        for s in candidate_slots:
            # Check student group clashes
            has_group_conflict = any(
                f"{grp.group_id}_{s.slot_id}" in group_occupied_slots
                for grp in occ.student_groups
            )
            if has_group_conflict:
                continue

            cohort_free_slots.append(s)

            # Check lecturer clashes
            has_lec_conflict = any(
                f"{lid}_{s.slot_id}" in lecturer_occupied_slots
                for lid in occ.lecturer_ids
            )
            if not has_lec_conflict:
                cohort_and_lec_free_slots.append(s)

                # Check venue availability in this slot (not occupied AND not pre-blocked)
                occupied_in_slot = slot_venue_occupancy[s.slot_id]
                has_free_allowed_venue = _any_allowed_venue_free(
                    slot_id=s.slot_id,
                    allowed_venue_ids=allowed_venue_ids,
                    occupied_in_slot=occupied_in_slot,
                    problem=problem,
                )
                if has_free_allowed_venue:
                    ideal_slots.append(s)

        if ideal_slots:
            chosen_slot = random.choice(ideal_slots)
        elif cohort_and_lec_free_slots:
            chosen_slot = random.choice(cohort_and_lec_free_slots)
        elif cohort_free_slots:
            chosen_slot = random.choice(cohort_free_slots)
        else:
            chosen_slot = random.choice(candidate_slots)

        # 3. Choose venue using capacity-proportional best-fit, avoiding pre-blocked slots
        chosen_venue_id = pick_venue_avoiding_blocked(
            expected_students=occ.expected_students,
            allowed_venue_ids=allowed_venue_ids,
            venues=problem.venues,
            slot_id=chosen_slot.slot_id,
            problem=problem,
            occupied_venue_ids=slot_venue_occupancy[chosen_slot.slot_id],
        )

        # Record assigned day, cohort slots, lecturer slots, and venue occupancy
        course_assigned_days[cid].add(chosen_slot.day)
        for grp in occ.student_groups:
            group_occupied_slots.add(f"{grp.group_id}_{chosen_slot.slot_id}")
        for lid in occ.lecturer_ids:
            lecturer_occupied_slots.add(f"{lid}_{chosen_slot.slot_id}")
        slot_venue_occupancy[chosen_slot.slot_id].add(chosen_venue_id)

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
