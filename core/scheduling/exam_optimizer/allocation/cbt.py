"""Throughput-based CBT venue and turn allocation."""

from math import ceil
from typing import Any, Dict, List, Optional, Tuple

from ..preprocessing.venues import get_venue_capacity


def allocate_cbt_venues(
    venues: List[Any],
    student_count: int,
    per_student_duration: Optional[int],
    base_duration: Optional[int] = 30,
) -> Optional[Tuple[int, List[Dict[str, Any]]]]:
    """Allocates CBT centres, turns, and parallel streams for a student population.

    Throughput model:
    - Multiple computer centres operate in parallel during a common exam window.
    - Turns are calculated across the total available simultaneous capacity.
    - Duration is driven by: longest_turns * per_student_duration.

    Returns:
        (total_duration_minutes, [venue_allocation_dicts]) or None if infeasible.
    """
    capacities = [(v, get_venue_capacity(v)) for v in venues]
    capacities = [(v, c) for v, c in capacities if c > 0]
    if not capacities:
        return None

    # Sort descending by capacity to prioritize the largest centres
    capacities.sort(key=lambda item: (-item[1], getattr(item[0], "name", "")))
    total_capacity = sum(cap for _, cap in capacities)
    if total_capacity <= 0:
        return None

    longest_turns = ceil(student_count / total_capacity)
    remaining = student_count
    allocations = []

    for venue, cap in capacities:
        assigned = min(cap * longest_turns, remaining)
        if assigned > 0:
            turns = ceil(assigned / cap)
            allocations.append(
                {
                    "venue_id": venue.id,
                    "venue_name": venue.name,
                    "students": assigned,
                    "turns": turns,
                    "capacity": cap,
                }
            )
            remaining -= assigned
        if remaining == 0:
            break

    unit_dur = per_student_duration or base_duration or 30
    actual_duration = max(1, longest_turns * unit_dur)

    return actual_duration, allocations

