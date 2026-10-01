import random
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem
from .chromosome import Chromosome
from .venue_utils import pick_best_fit_venue

ALL_WEEKDAYS = ("MO", "TU", "WE", "TH", "FR")


def repair_chromosome(
    chromosome: Chromosome,
    problem: SchedulingProblem,
) -> Chromosome:
    """
    Post-crossover/mutation repair operator:
      1. Resolves duplicate day placements for multi-occurrence courses.
      2. Ensures assigned venues are strictly members of allowed_venues_by_course with best-fit capacity.
      3. Resolves venue double-bookings (prioritizing larger cohorts for larger rooms).
      4. Resolves student cohort timetable clashes.
      5. Resolves lecturer double-booking.
    """
    assignments = list(chromosome.assignments)
    repaired = False

    # -------------------------------------------------------------
    # 1. Check multi-occurrence courses for same-day duplicates
    # -------------------------------------------------------------
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
                unused_days = [d for d in ALL_WEEKDAYS if d not in assigned_days]
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

    # -------------------------------------------------------------
    # 2. Check allowed venues validity & best-fit capacity
    # -------------------------------------------------------------
    for i, a in enumerate(assignments):
        cid = a.course_id
        allowed = problem.allowed_venues_by_course.get(cid, [])
        if allowed and a.venue_id not in allowed:
            best_vid = pick_best_fit_venue(
                expected_students=a.occurrence.expected_students,
                allowed_venue_ids=allowed,
                venues=problem.venues,
            )
            assignments[i] = Assignment(
                occurrence=a.occurrence,
                slot=a.slot,
                venue_id=best_vid,
            )
            repaired = True

    # -------------------------------------------------------------
    # 3. Resolve venue double-bookings (exact same slot & venue)
    # -------------------------------------------------------------
    slot_venue_map: Dict[Tuple[str, int | str], List[int]] = defaultdict(list)
    slot_occupied_venues: Dict[str, Set[int | str]] = defaultdict(set)

    for i, a in enumerate(assignments):
        slot_venue_map[(a.slot.slot_id, a.venue_id)].append(i)
        slot_occupied_venues[a.slot.slot_id].add(a.venue_id)

    for (slot_id, venue_id), indices in list(slot_venue_map.items()):
        if len(indices) <= 1:
            continue

        # Sort indices: prioritize larger cohort keeping the room
        indices.sort(key=lambda idx: assignments[idx].occurrence.expected_students, reverse=True)

        # The first occurrence keeps the venue; relocate the rest
        for clash_idx in indices[1:]:
            clash_a = assignments[clash_idx]
            occ = clash_a.occurrence
            allowed = problem.allowed_venues_by_course.get(occ.course_id, [])
            if not allowed:
                allowed = list(problem.venues.keys())

            occupied_here = slot_occupied_venues[slot_id]
            free_in_slot = [vid for vid in allowed if vid not in occupied_here]

            if free_in_slot:
                # Find best-fit among free venues in the same slot
                new_vid = pick_best_fit_venue(
                    expected_students=occ.expected_students,
                    allowed_venue_ids=free_in_slot,
                    venues=problem.venues,
                )
                assignments[clash_idx] = Assignment(
                    occurrence=occ,
                    slot=clash_a.slot,
                    venue_id=new_vid,
                )
                slot_occupied_venues[slot_id].add(new_vid)
                repaired = True
            else:
                # Relocate to another slot that has a free allowed venue
                alt_slots = [s for s in problem.valid_slots if s.slot_id != slot_id]
                random.shuffle(alt_slots)

                relocated = False
                for candidate_slot in alt_slots:
                    free_venues = [
                        vid
                        for vid in allowed
                        if vid not in slot_occupied_venues[candidate_slot.slot_id]
                    ]
                    if free_venues:
                        new_vid = pick_best_fit_venue(
                            expected_students=occ.expected_students,
                            allowed_venue_ids=free_venues,
                            venues=problem.venues,
                        )
                        assignments[clash_idx] = Assignment(
                            occurrence=occ,
                            slot=candidate_slot,
                            venue_id=new_vid,
                        )
                        slot_occupied_venues[candidate_slot.slot_id].add(new_vid)
                        repaired = True
                        relocated = True
                        break

                if not relocated and alt_slots:
                    # Fallback slot
                    new_slot = alt_slots[0]
                    new_vid = pick_best_fit_venue(
                        expected_students=occ.expected_students,
                        allowed_venue_ids=allowed,
                        venues=problem.venues,
                    )
                    assignments[clash_idx] = Assignment(
                        occurrence=occ,
                        slot=new_slot,
                        venue_id=new_vid,
                    )
                    repaired = True

    # -------------------------------------------------------------
    # 4. Resolve student cohort conflicts in the same slot
    # -------------------------------------------------------------
    slot_assignments: Dict[str, List[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        slot_assignments[a.slot.slot_id].append(i)

    for slot_id, indices in slot_assignments.items():
        if len(indices) < 2:
            continue

        n = len(indices)
        for i_pos in range(n):
            idx1 = indices[i_pos]
            a1 = assignments[idx1]
            conflicts = problem.student_conflict_graph.get(a1.course_id)
            if not conflicts:
                continue

            for j_pos in range(i_pos + 1, n):
                idx2 = indices[j_pos]
                a2 = assignments[idx2]

                if a2.course_id in conflicts:
                    # Found a student conflict between a1 and a2!
                    # Relocate a2 (or whichever has fewer total occurrences)
                    move_idx = idx2
                    target_a = a2
                    occ = target_a.occurrence

                    # Days already used by this course
                    used_days = {
                        assignments[k].slot.day
                        for k in course_indices.get(target_a.course_id, [])
                        if k != move_idx
                    }

                    # Find a slot where this course's cohort has no conflict
                    allowed_vids = problem.allowed_venues_by_course.get(occ.course_id, [])
                    if not allowed_vids:
                        allowed_vids = list(problem.venues.keys())

                    best_candidate_slot = None
                    alt_slots = [
                        s
                        for s in problem.valid_slots
                        if s.slot_id != slot_id and s.day not in used_days
                    ]
                    if not alt_slots:
                        alt_slots = [s for s in problem.valid_slots if s.slot_id != slot_id]
                    random.shuffle(alt_slots)

                    for s in alt_slots:
                        # Check if any course already in `s` conflicts with `occ`
                        current_in_s = slot_assignments.get(s.slot_id, [])
                        clash_found = any(
                            assignments[k].course_id in conflicts for k in current_in_s
                        )
                        if not clash_found:
                            best_candidate_slot = s
                            break

                    chosen_slot = best_candidate_slot or (alt_slots[0] if alt_slots else target_a.slot)
                    new_vid = pick_best_fit_venue(
                        expected_students=occ.expected_students,
                        allowed_venue_ids=allowed_vids,
                        venues=problem.venues,
                        occupied_venue_ids=slot_occupied_venues[chosen_slot.slot_id],
                    )

                    assignments[move_idx] = Assignment(
                        occurrence=occ,
                        slot=chosen_slot,
                        venue_id=new_vid,
                    )
                    repaired = True

    # -------------------------------------------------------------
    # 5. Resolve lecturer double-bookings in the same slot
    # -------------------------------------------------------------
    slot_assignments = defaultdict(list)
    for i, a in enumerate(assignments):
        slot_assignments[a.slot.slot_id].append(i)

    for slot_id, indices in slot_assignments.items():
        if len(indices) < 2:
            continue

        lecturer_map: Dict[int | str, List[int]] = defaultdict(list)
        for idx in indices:
            for lid in assignments[idx].occurrence.lecturer_ids:
                lecturer_map[lid].append(idx)

        for lid, lec_indices in lecturer_map.items():
            if len(lec_indices) <= 1:
                continue

            for move_idx in lec_indices[1:]:
                target_a = assignments[move_idx]
                occ = target_a.occurrence
                allowed_vids = problem.allowed_venues_by_course.get(occ.course_id, list(problem.venues.keys()))

                used_days = {
                    assignments[k].slot.day
                    for k in course_indices.get(target_a.course_id, [])
                    if k != move_idx
                }

                alt_slots = [
                    s for s in problem.valid_slots
                    if s.slot_id != slot_id and s.day not in used_days
                ]
                if not alt_slots:
                    alt_slots = [s for s in problem.valid_slots if s.slot_id != slot_id]
                random.shuffle(alt_slots)

                for s in alt_slots:
                    current_in_s = slot_assignments.get(s.slot_id, [])
                    lec_busy = any(
                        lid in assignments[k].occurrence.lecturer_ids for k in current_in_s
                    )
                    stu_busy = any(
                        assignments[k].course_id in problem.student_conflict_graph.get(target_a.course_id, set())
                        for k in current_in_s
                    )
                    if not lec_busy and not stu_busy:
                        new_vid = pick_best_fit_venue(
                            expected_students=occ.expected_students,
                            allowed_venue_ids=allowed_vids,
                            venues=problem.venues,
                            occupied_venue_ids=slot_occupied_venues[s.slot_id],
                        )
                        assignments[move_idx] = Assignment(
                            occurrence=occ,
                            slot=s,
                            venue_id=new_vid,
                        )
                        repaired = True
                        break

    # -------------------------------------------------------------
    # 6. Smooth cohort daily distribution to stay within daily limits
    # -------------------------------------------------------------
    max_daily = problem.daily_lecture_limit
    cohort_day_indices: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, a in enumerate(assignments):
        for grp in a.occurrence.student_groups:
            cohort_day_indices[(grp.group_id, a.slot.day)].append(i)

    for (grp_id, day), indices in list(cohort_day_indices.items()):
        if len(indices) <= max_daily:
            continue

        cohort_counts_by_day = {
            d: len(cohort_day_indices.get((grp_id, d), [])) for d in ALL_WEEKDAYS
        }

        excess_count = len(indices) - max_daily
        for excess_idx in range(excess_count):
            move_gene_idx = indices[len(indices) - 1 - excess_idx]
            target_a = assignments[move_gene_idx]
            occ = target_a.occurrence

            candidate_days = [
                d for d in ALL_WEEKDAYS
                if d != day and cohort_counts_by_day[d] < max_daily
            ]
            if not candidate_days:
                min_count = min(cohort_counts_by_day.values())
                candidate_days = [d for d in ALL_WEEKDAYS if d != day and cohort_counts_by_day[d] == min_count]

            if not candidate_days:
                continue

            course_used_days = {
                assignments[k].slot.day
                for k in course_indices.get(target_a.course_id, [])
                if k != move_gene_idx
            }
            valid_target_days = [d for d in candidate_days if d not in course_used_days]
            if not valid_target_days:
                valid_target_days = candidate_days

            target_day = random.choice(valid_target_days)
            alt_slots = [s for s in problem.valid_slots if s.day == target_day]
            random.shuffle(alt_slots)

            allowed_vids = problem.allowed_venues_by_course.get(occ.course_id, list(problem.venues.keys()))

            for s in alt_slots:
                current_in_s = slot_assignments.get(s.slot_id, [])
                has_stu_clash = any(
                    assignments[k].course_id in problem.student_conflict_graph.get(target_a.course_id, set())
                    for k in current_in_s
                )
                has_lec_clash = any(
                    any(lid in assignments[k].occurrence.lecturer_ids for lid in occ.lecturer_ids)
                    for k in current_in_s
                )
                occupied_in_s = {assignments[k].venue_id for k in current_in_s}
                free_vids = [vid for vid in allowed_vids if vid not in occupied_in_s]

                if not has_stu_clash and not has_lec_clash and free_vids:
                    new_vid = pick_best_fit_venue(
                        expected_students=occ.expected_students,
                        allowed_venue_ids=free_vids,
                        venues=problem.venues,
                    )
                    assignments[move_gene_idx] = Assignment(
                        occurrence=occ,
                        slot=s,
                        venue_id=new_vid,
                    )
                    cohort_counts_by_day[day] -= 1
                    cohort_counts_by_day[target_day] += 1
                    repaired = True
                    break

    return Chromosome(assignments) if repaired else chromosome


def final_repair_pass(
    chromosome: Chromosome,
    problem: SchedulingProblem,
    max_passes: int = 15,
) -> Chromosome:
    """
    Thorough deterministic repair pass run post-GA on the best chromosome:
    Iteratively resolves remaining hard conflicts (venue clashes, student clashes,
    lecturer clashes, and day duplicates) until zero hard conflicts are achieved
    or stagnation is reached.
    """
    from ..evaluation.evaluator import evaluate

    current_chrome = chromosome
    best_eval = evaluate(current_chrome.assignments, problem)

    if best_eval.hard_conflicts == 0:
        return current_chrome

    for pass_num in range(max_passes):
        repaired_chrome = repair_chromosome(current_chrome, problem)
        new_eval = evaluate(repaired_chrome.assignments, problem)

        if new_eval.hard_conflicts < best_eval.hard_conflicts:
            current_chrome = repaired_chrome
            best_eval = new_eval
        elif new_eval.hard_conflicts == best_eval.hard_conflicts and new_eval.capacity_penalty < best_eval.capacity_penalty:
            current_chrome = repaired_chrome
            best_eval = new_eval

        if best_eval.hard_conflicts == 0:
            break

        # Targeted greedy pass on remaining hard conflicts
        assignments = list(current_chrome.assignments)
        conflict_resolved = False

        # Group assignments by slot
        slot_map: Dict[str, List[int]] = defaultdict(list)
        for i, a in enumerate(assignments):
            slot_map[a.slot.slot_id].append(i)

        # 1. Resolve any remaining venue clashes
        slot_venue_occupancy: Dict[Tuple[str, int | str], List[int]] = defaultdict(list)
        for i, a in enumerate(assignments):
            slot_venue_occupancy[(a.slot.slot_id, a.venue_id)].append(i)

        for (slot_id, venue_id), indices in slot_venue_occupancy.items():
            if len(indices) > 1:
                # Move the secondary occurrence
                move_idx = indices[1]
                a = assignments[move_idx]
                occ = a.occurrence
                allowed = problem.allowed_venues_by_course.get(occ.course_id, list(problem.venues.keys()))

                # Try to find a slot & venue that generates 0 hard conflicts
                for candidate_slot in problem.valid_slots:
                    # Check if this course is already on this day
                    same_day_used = any(
                        assignments[k].course_id == a.course_id and assignments[k].slot.day == candidate_slot.day
                        for k in range(len(assignments))
                        if k != move_idx
                    )
                    if same_day_used:
                        continue

                    # Check student clashes in candidate slot
                    conflicting_cids = problem.student_conflict_graph.get(a.course_id, set())
                    has_stu_clash = any(
                        assignments[k].course_id in conflicting_cids
                        for k in slot_map.get(candidate_slot.slot_id, [])
                    )
                    if has_stu_clash:
                        continue

                    # Check lecturer clashes in candidate slot
                    has_lec_clash = any(
                        any(lid in assignments[k].occurrence.lecturer_ids for lid in occ.lecturer_ids)
                        for k in slot_map.get(candidate_slot.slot_id, [])
                    )
                    if has_lec_clash:
                        continue

                    # Check venue availability in candidate slot
                    occupied_in_cand = {
                        assignments[k].venue_id for k in slot_map.get(candidate_slot.slot_id, [])
                    }
                    free_allowed = [vid for vid in allowed if vid not in occupied_in_cand]
                    if free_allowed:
                        best_vid = pick_best_fit_venue(
                            expected_students=occ.expected_students,
                            allowed_venue_ids=free_allowed,
                            venues=problem.venues,
                        )
                        assignments[move_idx] = Assignment(
                            occurrence=occ,
                            slot=candidate_slot,
                            venue_id=best_vid,
                        )
                        conflict_resolved = True
                        break

        if conflict_resolved:
            current_chrome = Chromosome(assignments)
            best_eval = evaluate(current_chrome.assignments, problem)
            if best_eval.hard_conflicts == 0:
                break

    return current_chrome
