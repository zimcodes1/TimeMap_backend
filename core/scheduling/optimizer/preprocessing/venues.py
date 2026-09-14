from typing import Dict, List

from ..models.course import CourseData
from ..models.venue import VenueData


def filter_allowed_venues(
    course: CourseData,
    all_venues: List[VenueData],
) -> List[int | str]:
    """
    Resolves the allowed venues for a given course prior to GA initialization:
      - Practical courses MUST use laboratories.
      - Ordinary lecture courses MUST use lecture halls or multipurpose halls (never labs).
    If course.allowed_venue_ids is explicitly provided, only venues in that list matching
    the type constraint are included.
    """
    is_practical = course.is_practical
    explicit_ids = set(course.allowed_venue_ids) if course.allowed_venue_ids else None

    allowed: List[int | str] = []
    for venue in all_venues:
        if explicit_ids is not None and venue.id not in explicit_ids:
            continue

        if is_practical:
            if venue.is_laboratory:
                allowed.append(venue.id)
        else:
            if not venue.is_laboratory:
                allowed.append(venue.id)

    # Fallback safety: if no strict venue matches, return all appropriate by type
    if not allowed:
        for venue in all_venues:
            if is_practical and venue.is_laboratory:
                allowed.append(venue.id)
            elif not is_practical and not venue.is_laboratory:
                allowed.append(venue.id)

    # Final fallback if absolutely no matching type exists in database
    if not allowed and all_venues:
        allowed = [all_venues[0].id]

    return allowed


def build_allowed_venues_map(
    courses: List[CourseData],
    all_venues: List[VenueData],
) -> Dict[int | str, List[int | str]]:
    """
    Builds a map of course_id -> list of allowed venue_ids for all courses.
    """
    return {c.id: filter_allowed_venues(c, all_venues) for c in courses}

