from dataclasses import dataclass, field
from typing import Optional, Tuple

from .student_group import StudentGroup


@dataclass(frozen=True)
class CourseData:
    """
    Representation of an academic course to be scheduled.
    """

    id: int | str
    code: str
    title: str
    level: int
    department_id: int | str
    department_name: str = ""
    required_occurrences: int = 1
    course_type: str = "lecture"  # "lecture" or "practical"
    student_groups: Tuple[StudentGroup, ...] = field(default_factory=tuple)
    lecturer_ids: Tuple[int | str, ...] = field(default_factory=tuple)
    allowed_venue_ids: Tuple[int | str, ...] = field(default_factory=tuple)
    expected_students: int = 50
    owning_level: str = "department"  # "department", "faculty", "school", "general"
    faculty_id: Optional[int | str] = None
    school_id: Optional[int | str] = None
    receiving_department_ids: Tuple[int | str, ...] = field(default_factory=tuple)
    is_general: bool = False

    @property
    def is_practical(self) -> bool:
        return self.course_type.lower() == "practical"

    def __str__(self) -> str:
        return f"{self.code} ({self.course_type}, occ={self.required_occurrences})"

