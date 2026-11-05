"""Venue resolution and compatibility filtering for exam scheduling."""

from typing import Any, List
from django.db.models import Q

from courses.models import Course
from hierarchy.models import Department, Faculty
from venues.models import Venue


def resolve_scope_venues(scope_type: str, scope_id: int) -> List[Venue]:
    """Queries all active venues accessible to the given administrative scope."""
    qs = Venue.objects.filter(is_active=True)

    if scope_type == "department":
        department = Department.objects.select_related("faculty__school").get(pk=scope_id)
        qs = qs.filter(
            Q(owning_department_id=scope_id)
            | Q(owning_faculty=department.faculty)
            | Q(owning_level="school", owning_school=department.faculty.school)
        )
    elif scope_type == "faculty":
        faculty = Faculty.objects.get(pk=scope_id)
        qs = qs.filter(
            Q(owning_faculty_id=scope_id)
            | Q(owning_department__faculty_id=scope_id)
            | Q(owning_level="school", owning_school=faculty.school)
        )
    elif scope_type == "school":
        qs = qs.filter(
            Q(owning_school_id=scope_id)
            | Q(owning_faculty__school_id=scope_id)
            | Q(owning_department__faculty__school_id=scope_id)
        )
    else:
        raise ValueError(f"Unknown examination scope type: {scope_type}")

    return list(qs.distinct().order_by("name"))


def filter_venues_by_exam_type(venues: List[Venue], exam_type: str) -> List[Venue]:
    """Filters a collection of venues for physical compatibility with the exam type."""
    filtered = []
    for v in venues:
        cap = int(getattr(v, "exam_capacity", None) or getattr(v, "capacity", None) or 0)
        if cap <= 0:
            continue

        if exam_type == Course.ExamType.CBT:
            # CBT exams are strictly scheduled to CBT Exam Centers only
            # (computer labs, general laboratories, and lecture halls are not eligible)
            if getattr(v, "venue_type", "") in [Venue.VenueType.CBT_CENTER, Venue.VenueType.EXAM_HALL]:
                filtered.append(v)
        elif exam_type == Course.ExamType.LAB_PRACTICAL:
            # Lab practical exams are scheduled to laboratory venues
            if getattr(v, "venue_type", "") in [Venue.VenueType.LABORATORY, "lab"]:
                filtered.append(v)
        else:
            # Written exams use lecture halls, auditoriums, and multipurpose halls
            # (strictly excluding laboratories and CBT exam centers)
            if getattr(v, "venue_type", "") not in [
                Venue.VenueType.LABORATORY,
                "lab",
                Venue.VenueType.CBT_CENTER,
                Venue.VenueType.EXAM_HALL,
            ]:
                filtered.append(v)

    return filtered


def get_venue_capacity(venue: Any) -> int:
    """Returns the effective exam seating capacity of a venue."""
    return int(getattr(venue, "exam_capacity", None) or getattr(venue, "capacity", None) or 0)

