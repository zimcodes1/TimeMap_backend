from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ExamPopulation:
    """Represents a student cohort from a specific academic offering."""

    course_id: int
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    program_id: Optional[int] = None
    program_name: Optional[str] = None
    level: int = 100
    student_count: int = 0
    student_ids: Set[int | str] = field(default_factory=set)


@dataclass
class ExamEvent:
    """Logical examination event for an academic course."""

    course_id: int
    course_code: str
    course_title: str
    course_level: int
    exam_type: str  # "written", "cbt", "lab_practical"
    duration_minutes: int
    duration_per_student_minutes: Optional[int] = None
    student_count: int = 0
    student_ids: Set[int | str] = field(default_factory=set)
    populations: List[ExamPopulation] = field(default_factory=list)
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    program_id: Optional[int] = None
    program_name: Optional[str] = None

    # Precomputed difficulty metrics for constructive placement heuristic
    conflict_degree: int = 0
    venue_scarcity: float = 0.0

    @property
    def has_registered_students(self) -> bool:
        return bool(self.student_ids)

    def to_event_payload(self) -> Dict[str, Any]:
        """Converts logical properties to a template event dict."""
        return {
            "course_id": self.course_id,
            "course_code": self.course_code,
            "course_title": self.course_title,
            "course_level": self.course_level,
            "department_id": self.department_id,
            "department_name": self.department_name,
            "program_id": self.program_id,
            "program_name": self.program_name,
            "exam_type": self.exam_type,
            "student_count": self.student_count,
            "joined_courses": [],
        }

