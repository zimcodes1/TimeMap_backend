from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

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

    # Pre-existing slot occupancy from ancestor and peer published timetables.
    # Maps venue_id -> set of slot_ids (e.g. "MO_08:00-10:00") already occupied.
    blocked_venue_slots: Dict[int | str, Set[str]] = field(default_factory=dict)
    # Maps lecturer_id -> set of slot_ids already occupied by external schedules.
    blocked_lecturer_slots: Dict[int | str, Set[str]] = field(default_factory=dict)
    # Maps (program_id, level) -> set of slot_ids already occupied by external schedules.
    blocked_cohort_slots: Dict[Tuple[int, int], Set[str]] = field(default_factory=dict)
    # Detailed metadata for conflict diagnostics
    external_commitments_details: List[Dict[str, Any]] = field(default_factory=list)

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
