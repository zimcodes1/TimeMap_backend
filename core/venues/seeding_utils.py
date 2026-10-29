"""
Shared utility module for seeding realistic faculty and departmental venues in TimeMapper.

Enforces:
1. Strict restriction: NO CBT Exam Centers or Exam Halls (only lecture halls, laboratories,
   auditoriums, and multipurpose rooms/studios).
2. Realistic capacity and proportional exam capacity.
3. Clean facility association (projectors, whiteboards, sound systems, labs, etc.).
4. Accurate hierarchical ownership (School, Faculty, Department).
"""

from typing import List, Optional, Tuple
from django.db import transaction

from hierarchy.models import Department, Faculty, School
from venues.models import Facility, Venue


# Disallowed venue types per strict user constraint
DISALLOWED_TYPES = {
    Venue.VenueType.CBT_CENTER,
    Venue.VenueType.EXAM_HALL,
}


def ensure_facility(name: str) -> Facility:
    """Gets or creates a Facility amenity."""
    fac, _ = Facility.objects.get_or_create(name=name.strip())
    return fac


def ensure_venue(
    name: str,
    code: str,
    venue_type: str,
    capacity: int,
    exam_capacity: Optional[int],
    location: str,
    owning_level: str,
    school: School,
    faculty: Optional[Faculty] = None,
    department: Optional[Department] = None,
    facilities: Optional[List[str]] = None,
    is_active: bool = True,
) -> Tuple[Venue, bool]:
    """
    Creates or updates a Venue idempotently.

    Raises:
        ValueError if the venue_type is a CBT center or exam hall.
    """
    if venue_type in DISALLOWED_TYPES or "cbt" in venue_type.lower() or "exam" in venue_type.lower():
        raise ValueError(
            f"Venue '{name}' has disallowed venue type '{venue_type}'. "
            "CBT Exam Centers and dedicated Exam Halls are prohibited."
        )

    # Calculate default exam capacity if not provided (typically ~60% of lecture capacity)
    if exam_capacity is None:
        exam_capacity = max(1, int(capacity * 0.6))

    defaults = {
        "code": code,
        "venue_type": venue_type,
        "capacity": capacity,
        "exam_capacity": exam_capacity,
        "location": location,
        "owning_level": owning_level,
        "owning_school": school,
        "owning_faculty": faculty,
        "owning_department": department,
        "is_active": is_active,
    }

    venue, created = Venue.objects.update_or_create(
        name=name,
        defaults=defaults,
    )

    if facilities:
        fac_objs = [ensure_facility(f_name) for f_name in facilities]
        venue.facilities.set(fac_objs)

    return venue, created
