"""Unified venue allocation planner facade."""

from typing import Any, Dict, List, Optional, Tuple

from courses.models import Course

from .cbt import allocate_cbt_venues
from .written import allocate_written_venues


def allocate_venues(
    venues: List[Any],
    count: int,
    exam_type: str,
    duration: int,
    per_student: Optional[int] = None,
) -> Optional[Tuple[int, List[Dict[str, Any]]]]:
    """Dispatches venue allocation to the type-specific strategy.

    Provides exact parity with legacy _allocate() helper for written, CBT, and practical exams.
    """
    if exam_type != Course.ExamType.CBT:
        return allocate_written_venues(venues, count, duration)
    return allocate_cbt_venues(venues, count, per_student, duration)

