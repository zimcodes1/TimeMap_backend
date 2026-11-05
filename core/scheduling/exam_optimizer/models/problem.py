from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from .event import ExamEvent
from .time_window import CalendarPolicy, CandidateWindow


@dataclass
class ExamSchedulingProblem:
    """Pure, immutable data representation of the complete examination scheduling problem."""

    semester_id: int | str
    semester_label: str
    scope_type: str  # "department", "faculty", "school"
    scope_id: int
    scope_name: str
    start_date: date
    end_date: date

    # Logical demand
    events: Dict[int, ExamEvent] = field(default_factory=dict)

    # Physical resources grouped by exam type ("written", "cbt", "lab_practical")
    venues_by_type: Dict[str, List[Any]] = field(default_factory=dict)

    # Precomputed conflict graph: course_id -> set of conflicting course_ids
    student_conflict_graph: Dict[int, Set[int]] = field(default_factory=dict)

    # Precomputed pairwise cohort Jaccard similarity
    cohort_overlaps: Dict[Tuple[int, int], float] = field(default_factory=dict)

    # Feasible calendar windows within the semester exam period
    candidate_windows: List[CandidateWindow] = field(default_factory=list)

    # Calendar operating policy
    policy: CalendarPolicy = field(default_factory=CalendarPolicy)

    # Pre-existing commitments from ancestor and peer published timetables
    # Maps venue_id -> list of occupied window dicts: {date, start_time, end_time, course_code, scope}
    blocked_venue_windows: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)
    # Maps (program_id, level) -> list of occupied window dicts
    blocked_cohort_windows: Dict[Tuple[int, int], List[Dict[str, Any]]] = field(default_factory=dict)
    # Maps student_id -> list of occupied window dicts
    blocked_student_windows: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)
    # Diagnostic breakdown of external commitments
    external_commitments_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_events(self) -> int:
        return len(self.events)

    @property
    def total_students(self) -> int:
        return sum(event.student_count for event in self.events.values())

    @property
    def ordered_events(self) -> List[ExamEvent]:
        """Events sorted by difficulty heuristic descending, with tie break by course code."""
        return sorted(
            self.events.values(),
            key=lambda e: (-e.student_count, e.course_code),
        )

