"""Physical venue allocation logic for written and laboratory examinations."""

from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

from ..preprocessing.venues import get_venue_capacity


def allocate_written_venues(
    venues: List[Any],
    student_count: int,
    base_duration: int,
) -> Optional[Tuple[int, List[Dict[str, Any]]]]:
    """Allocates one or more physical rooms for a written examination.

    Strategy:
    1. Single Venue: Prefer the room with sufficient capacity whose excess (capacity - count) is minimized.
    2. Venue Pair: If no single room accommodates the cohort, evaluate combinations of 2 rooms.
       Select the pair minimizing total excess capacity and capacity imbalance.
    3. Multi-Venue Greedy: If no pair suffices, greedily allocate across largest available rooms.

    Returns:
        (duration_minutes, [allocation_dicts]) or None if infeasible.
    """
    capacities = [(v, get_venue_capacity(v)) for v in venues]
    capacities = [(v, c) for v, c in capacities if c > 0]
    if not capacities:
        return None

    capacities.sort(key=lambda item: (item[1], getattr(item[0], "name", "")))

    # 1. Single Venue Search
    capable_singles = [(v, c) for v, c in capacities if c >= student_count]
    if capable_singles:
        chosen_venue, chosen_cap = min(
            capable_singles,
            key=lambda item: (item[1] - student_count, getattr(item[0], "name", "")),
        )
        return base_duration, [
            {
                "venue_id": chosen_venue.id,
                "venue_name": chosen_venue.name,
                "students": student_count,
                "turns": 1,
                "capacity": chosen_cap,
            }
        ]

    # 2. Venue Pair Search
    candidate_pairs = [
        (pair, sum(cap for _, cap in pair) - student_count, abs(pair[0][1] - pair[1][1]))
        for pair in combinations(capacities, 2)
        if sum(cap for _, cap in pair) >= student_count
    ]

    if candidate_pairs:
        best_pair, _, _ = min(
            candidate_pairs,
            key=lambda item: (
                item[1],  # minimum excess
                item[2],  # minimum capacity imbalance
                tuple(getattr(room, "name", "") for room, _ in item[0]),
            ),
        )
        selected = sorted(best_pair, key=lambda item: (-item[1], getattr(item[0], "name", "")))
    else:
        # 3. Multi-Venue Greedy Fallback
        selected = sorted(capacities, key=lambda item: (-item[1], getattr(item[0], "name", "")))

    remaining = student_count
    allocations = []
    for venue, cap in selected:
        if remaining <= 0:
            break
        assigned = min(cap, remaining)
        remaining -= assigned
        allocations.append(
            {
                "venue_id": venue.id,
                "venue_name": venue.name,
                "students": assigned,
                "turns": 1,
                "capacity": cap,
            }
        )

    if remaining <= 0:
        return base_duration, allocations
    return None

