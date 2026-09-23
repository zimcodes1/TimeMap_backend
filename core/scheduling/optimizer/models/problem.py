from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .course import CourseData
from .lecturer import LecturerData
from .occurrence import CourseOccurrence
from .slot import Slot
from .student_group import StudentGroup
from .venue import VenueData


@dataclass
class SchedulingProblem:
    """
    Complete, self-contained scheduling problem specification passed to the GA.
    Completely decoupled from the database.
    """

    occurrences: List[CourseOccurrence]
    valid_slots: List[Slot]
    venues: Dict[int | str, VenueData]
    student_conflict_graph: Dict[int | str, Set[int | str]]
    shared_student_groups: Dict[Tuple[int | str, int | str], List[StudentGroup]] = field(
        default_factory=dict
    )
    lecturers_by_course: Dict[int | str, Set[int | str]] = field(default_factory=dict)
    lecturer_details: Dict[int | str, LecturerData] = field(default_factory=dict)
    allowed_venues_by_course: Dict[int | str, List[int | str]] = field(
        default_factory=dict
    )
    daily_lecture_limit: int = 3

    # Metadata
    scope_type: str = "school"
    scope_id: int | str = ""
    scope_name: str = ""
    semester_id: int | str = ""

    # Index lookups
    occurrence_by_id: Dict[str, CourseOccurrence] = field(init=False)
    venues_by_id: Dict[int | str, VenueData] = field(init=False)

    def __post_init__(self):
        self.occurrence_by_id = {occ.occurrence_id: occ for occ in self.occurrences}
        self.venues_by_id = self.venues

    @property
    def total_occurrences(self) -> int:
        return len(self.occurrences)

    @property
    def lecturers(self) -> Dict[int | str, LecturerData]:
        return self.lecturer_details

