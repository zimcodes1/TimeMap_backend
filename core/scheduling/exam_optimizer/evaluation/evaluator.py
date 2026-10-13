"""Evaluation of candidate examination schedules."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..constraints.calendar import check_calendar_constraints
from ..constraints.conflicts import check_student_conflicts
from ..constraints.venues import check_venue_constraints
from ..constraints.workload import calculate_student_workload, calculate_workload_penalty
from ..models.problem import ExamSchedulingProblem

# Penalty weights for exam evaluation
WEIGHT_STUDENT_CONFLICT = 10000
WEIGHT_VENUE_CONFLICT = 8000
WEIGHT_CALENDAR_VIOLATION = 10000
WEIGHT_CAPACITY_VIOLATION = 5000
WEIGHT_WORKLOAD_PENALTY = 1.0


@dataclass
class ExamEvaluationResult:
    """Outcome of evaluating a complete examination schedule."""

    student_conflicts: int = 0
    venue_conflicts: int = 0
    calendar_violations: int = 0
    capacity_violations: int = 0
    workload_penalty: float = 0.0
    venue_excess_penalty: float = 0.0

    total_weighted_penalty: float = 0.0
    fitness: float = 1.0
    conflict_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def hard_conflicts(self) -> int:
        return (
            self.student_conflicts
            + self.venue_conflicts
            + self.calendar_violations
            + self.capacity_violations
        )

    @property
    def is_feasible(self) -> bool:
        return self.hard_conflicts == 0

    @property
    def is_optimal(self) -> bool:
        return self.hard_conflicts == 0 and self.workload_penalty == 0.0

    @property
    def lexicographic_rank(self) -> Tuple[int, int, int, int, float]:
        return (
            self.calendar_violations,
            self.student_conflicts,
            self.venue_conflicts,
            self.capacity_violations,
            self.workload_penalty,
        )


def evaluate_exam_schedule(
    events: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
    problem: ExamSchedulingProblem,
) -> ExamEvaluationResult:
    """Evaluates scheduled events against all constraints and computes normalized quality metrics."""
    calendar_errors = check_calendar_constraints(events, problem.start_date, problem.end_date)
    student_errors = check_student_conflicts(events, scheduled_states)
    venue_errors = check_venue_constraints(events, scheduled_states)

    capacity_errors = [e for e in venue_errors if "capacity" in e.get("reason", "").lower()]
    direct_venue_clashes = [e for e in venue_errors if "Venue conflict" in e.get("reason", "")]

    workload_stats = calculate_student_workload(scheduled_states)
    workload_pen = calculate_workload_penalty(workload_stats)

    total_penalty = (
        len(calendar_errors) * WEIGHT_CALENDAR_VIOLATION
        + len(student_errors) * WEIGHT_STUDENT_CONFLICT
        + len(direct_venue_clashes) * WEIGHT_VENUE_CONFLICT
        + len(capacity_errors) * WEIGHT_CAPACITY_VIOLATION
        + workload_pen * WEIGHT_WORKLOAD_PENALTY
    )

    fitness = 1.0 / (1.0 + total_penalty)

    all_details = []
    all_details.extend(calendar_errors)
    all_details.extend(student_errors)
    all_details.extend(venue_errors)

    return ExamEvaluationResult(
        student_conflicts=len(student_errors),
        venue_conflicts=len(direct_venue_clashes),
        calendar_violations=len(calendar_errors),
        capacity_violations=len(capacity_errors),
        workload_penalty=workload_pen,
        total_weighted_penalty=total_penalty,
        fitness=fitness,
        conflict_details=all_details,
    )

