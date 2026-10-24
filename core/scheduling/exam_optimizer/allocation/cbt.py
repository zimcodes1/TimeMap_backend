"""Throughput-based CBT venue and turn allocation."""

from math import ceil
from typing import Any, Dict, List, Optional, Tuple

from ..preprocessing.venues import get_venue_capacity


def allocate_cbt_venues(
    venues: List[Any],
    student_count: int,
    per_student_duration: Optional[int],
    base_duration: Optional[int] = 30,
    venue_usage: Optional[Dict[int, int]] = None,
) -> Optional[Tuple[int, List[Dict[str, Any]]]]:
    """Allocates CBT centres, turns, and parallel streams for a student population.

    Throughput model:
    - Multiple computer centres operate in parallel during a common exam window.
    - Turns are calculated across the total available simultaneous capacity.
    - Single capable centre is preferred when population fits within it, balanced by usage.
    - Duration is driven by: longest_turns * per_student_duration.

    Returns:
        (total_duration_minutes, [venue_allocation_dicts]) or None if infeasible.
    """
    capacities = [(v, get_venue_capacity(v)) for v in venues]
    capacities = [(v, c) for v, c in capacities if c > 0]
    if not capacities:
        return None

    usage_map = venue_usage or {}
    unit_dur = per_student_duration or base_duration or 30

    # 1. Single venue best-fit: If cohort fits inside a single CBT center, pick the least-used capable center
    capable_singles = [(v, c) for v, c in capacities if c >= student_count]
    if capable_singles:
        chosen_venue, chosen_cap = min(
            capable_singles,
            key=lambda item: (
                usage_map.get(item[0].id, 0),
                item[1] - student_count,
                getattr(item[0], "name", ""),
            ),
        )
        return unit_dur, [
            {
                "venue_id": chosen_venue.id,
                "venue_name": chosen_venue.name,
                "students": student_count,
                "turns": 1,
                "capacity": chosen_cap,
            }
        ]

    # 2. Multi-centre parallel allocation for large cohorts exceeding single-centre capacity
    capacities.sort(key=lambda item: (-item[1], usage_map.get(item[0].id, 0), getattr(item[0], "name", "")))
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

    actual_duration = max(1, longest_turns * unit_dur)

    return actual_duration, allocations

