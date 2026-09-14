from dataclasses import dataclass, field
from typing import Tuple

from .student_group import StudentGroup


@dataclass(frozen=True)
class CourseOccurrence:
    """
    A single scheduled event instance of a course within the weekly cycle.
    If course.required_occurrences == 2, there are two distinct CourseOccurrences
    (e.g., MTH101-1 and MTH101-2), each mapped to one gene in the chromosome.
    """

    occurrence_id: str  # e.g., "CSC101-1"
    course_id: int | str
    course_code: str
    course_title: str
    occurrence_index: int  # 1-indexed (1, 2, ...)
    total_occurrences: int
    student_groups: Tuple[StudentGroup, ...] = field(default_factory=tuple)
    lecturer_ids: Tuple[int | str, ...] = field(default_factory=tuple)
    allowed_venue_ids: Tuple[int | str, ...] = field(default_factory=tuple)
    course_type: str = "lecture"
    expected_students: int = 50

    @property
    def is_practical(self) -> bool:
        return self.course_type.lower() == "practical"

    def __str__(self) -> str:
        return f"{self.occurrence_id} ({self.course_type})"

