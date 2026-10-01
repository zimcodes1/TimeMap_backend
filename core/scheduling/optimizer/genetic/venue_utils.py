import random
from typing import Dict, List, Optional, Set

from ..models.venue import VenueData


def pick_best_fit_venue(
    expected_students: int,
    allowed_venue_ids: List[int | str],
    venues: Dict[int | str, VenueData],
    occupied_venue_ids: Optional[Set[int | str]] = None,
) -> int | str:
    """
    Capacity-proportional venue selector:
    Selects the venue with the smallest sufficient capacity (best-fit)
    to prevent small cohorts from consuming large halls/auditoriums needed
    by larger cohorts.

    Prioritization:
      1. Prefers allowed venues that are not already occupied in the target slot.
      2. Among those, filters to 'fitting' venues where capacity >= expected_students.
      3. Sorts fitting venues ascending by capacity (closest fit first) and excludes
         excessively oversized venues when closer fitting rooms are available.
      4. If no venue is large enough, picks from the largest available undersized venues
         to minimize student overflow penalty.
    """
    if not allowed_venue_ids:
        # Fallback if no allowed venue IDs provided
        if venues:
            return random.choice(list(venues.keys()))
        return 0

    occupied = occupied_venue_ids or set()

    # Step 1: Divide allowed venues into free and occupied
    free_venue_ids = [vid for vid in allowed_venue_ids if vid not in occupied]
    candidate_ids = free_venue_ids if free_venue_ids else allowed_venue_ids

    fitting: List[tuple[int | str, int]] = []
    undersized: List[tuple[int | str, int]] = []

    for vid in candidate_ids:
        v = venues.get(vid)
        if not v:
            continue
        if v.capacity >= expected_students:
            fitting.append((vid, v.capacity))
        else:
            undersized.append((vid, v.capacity))

    # Step 2: If fitting venues exist, select from closest fit (smallest sufficient)
    if fitting:
        # Sort ascending by capacity
        fitting.sort(key=lambda item: item[1])
        min_fit_cap = fitting[0][1]

        # Filter out venues that are excessively oversized when closer fits exist
        cutoff = max(min_fit_cap * 2.0, expected_students * 2.0)
        reasonable_fits = [item for item in fitting if item[1] <= cutoff]
        pool = reasonable_fits if reasonable_fits else fitting

        # Pick from top 2 closest fits (or fewer if fewer exist)
        top_k = pool[: min(2, len(pool))]
        return random.choice(top_k)[0]

    # Step 3: If no candidate fits, pick largest undersized to minimize deficit
    if undersized:
        undersized.sort(key=lambda item: item[1], reverse=True)
        top_k = undersized[: min(2, len(undersized))]
        return random.choice(top_k)[0]

    # Fallback to random choice from candidate IDs
    return random.choice(candidate_ids) if candidate_ids else 0
