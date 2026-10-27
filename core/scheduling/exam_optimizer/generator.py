"""High-level facade and result encapsulation for the exam timetable optimizer."""

from dataclasses import dataclass
import time
from typing import Any, Callable, Dict, List, Optional

from scheduling.models import Semester

from .allocation.joining import join_compatible_sessions
from .evaluation.evaluator import ExamEvaluationResult, evaluate_exam_schedule
from .evaluation.report import generate_exam_conflict_report
from .models.problem import ExamSchedulingProblem
from .models.time_window import CalendarPolicy
from .preprocessing.pipeline import build_exam_problem_from_db
from .solver.repair import repair_conflicts
from .solver.search import search_exam_schedule
from .validation.report import build_exam_diagnostics
from .validation.validator import validate_exam_timetable


@dataclass
class ExamGenerationResult:
    """Standard generation result produced by the examination optimizer engine.

    Mirrors the lecture timetable GenerationResult pattern, holding rich structured
    diagnostics, evaluation reports, and metrics.

    Implements __iter__ and __getitem__ to support backward-compatible tuple unpacking:
        events, diagnostics = generate_exam_timetable(...)
    """

    status: str  # "OPTIMAL", "FEASIBLE", "BEST_AVAILABLE", "FAILED"
    events: List[Dict[str, Any]]
    diagnostics: Dict[str, Any]
    metrics: Dict[str, Any]
    fitness: float
    evaluation: ExamEvaluationResult
    conflict_report: Dict[str, Any]
    runtime_seconds: float
    problem: Optional[ExamSchedulingProblem] = None

    @property
    def is_feasible(self) -> bool:
        has_unscheduled = bool(self.diagnostics and self.diagnostics.get("unscheduled"))
        return self.evaluation.is_feasible and not has_unscheduled and self.status in ("OPTIMAL", "FEASIBLE")

    @property
    def hard_conflicts_count(self) -> int:
        return self.evaluation.hard_conflicts

    def __iter__(self):
        """Allows unpacking as `events, diagnostics = generate_exam_timetable(...)`."""
        return iter((self.events, self.diagnostics))

    def __getitem__(self, index: int):
        """Allows indexing like result[0] -> events, result[1] -> diagnostics."""
        return (self.events, self.diagnostics)[index]


def generate_exam_timetable(
    semester: Semester,
    scope_type: str,
    scope_id: int,
    policy: Optional[CalendarPolicy] = None,
) -> ExamGenerationResult:
    """High-level facade function executing the complete examination scheduling pipeline:

    1. Preprocessing: queries DB and builds an in-memory ExamSchedulingProblem.
    2. Solver Search: heuristic placement with physical room & CBT turn allocations.
    3. Session Joining: groups small compatible exams (max 2 courses per CBT session).
    4. Deterministic Repair: resolves any conflicting overlaps or capacity issues.
    5. Independent Validation: verifies hard invariants (H1 through H11).
    6. Reporting & Result Packaging: compiles diagnostics, conflict reports, and metrics.
    """
    started_at = time.perf_counter()

    # 1. Preprocessing pipeline
    problem = build_exam_problem_from_db(
        semester=semester,
        scope_type=scope_type,
        scope_id=scope_id,
        policy=policy,
    )

    # 2. Solver placement
    events, scheduled_states, unscheduled, windows_evaluated = search_exam_schedule(
        problem
    )

    # 3. CBT & small exam joining
    joined_count = join_compatible_sessions(events, scheduled_states)

    # 4. Deterministic repair pass
    events, scheduled_states = repair_conflicts(events, scheduled_states, problem)

    # 5. Independent validation
    validation_result = validate_exam_timetable(
        events=events,
        scheduled_states=scheduled_states,
        start_date=problem.start_date,
        end_date=problem.end_date,
        policy=problem.policy,
        problem=problem,
    )

    # 6. Build diagnostics matching API contract
    diagnostics = build_exam_diagnostics(
        events=events,
        unscheduled=unscheduled,
        scheduled_states=scheduled_states,
        validation_result=validation_result,
        candidate_windows_evaluated=windows_evaluated,
        joined_sessions_count=joined_count,
    )

    # 7. Constraint evaluation & scoring
    evaluation = evaluate_exam_schedule(events, scheduled_states, problem)
    elapsed = round(time.perf_counter() - started_at, 3)

    # Determine status
    if not validation_result.get("valid", False):
        status = "FAILED"
    elif not unscheduled and evaluation.is_optimal:
        status = "OPTIMAL"
    elif not unscheduled:
        status = "FEASIBLE"
    elif len(problem.events) == 0:
        status = "FEASIBLE"
    else:
        status = "BEST_AVAILABLE"

    # Quality score (0.0 to 1.0)
    total_events_count = max(1, len(problem.events))
    if evaluation.hard_conflicts == 0:
        quality_score = 0.90 + (0.10 * max(0.0, 1.0 - (evaluation.workload_penalty / 1000.0)))
    else:
        conflict_factor = max(0.0, 1.0 - (evaluation.hard_conflicts / total_events_count))
        quality_score = 0.80 * conflict_factor

    quality_score = round(min(1.0, max(0.0, quality_score)), 4)

    # Detailed conflict report
    conflict_report = generate_exam_conflict_report(
        evaluation=evaluation,
        total_events=len(events),
        quality_score=quality_score,
    )

    # Pre-calculated summary metrics
    allocations = [alloc for event in events for alloc in event["venues"]]
    utilization = [
        alloc["students"] / (alloc["capacity"] * max(1, alloc.get("turns", 1)))
        for alloc in allocations
        if alloc.get("capacity")
    ]
    errors = validation_result.get("errors", [])

    metrics = {
        "courses_total": len(events) + len(unscheduled),
        "courses_scheduled": len(events),
        "courses_unscheduled": len(unscheduled),
        "hard_conflicts": len(errors),
        "student_conflicts": sum("Student conflict" in item.get("reason", "") for item in errors),
        "venue_conflicts": sum("Venue conflict" in item.get("reason", "") for item in errors),
        "venue_allocations": len(allocations),
        "venues_used": len({alloc["venue_id"] for alloc in allocations}),
        "average_venue_utilization": round(sum(utilization) / len(utilization), 4) if utilization else 0.0,
        "active_exam_days": len({event["date"] for event in events}),
        "joined_sessions": joined_count,
        "cbt_turns": sum(
            alloc.get("turns", 0)
            for event in events
            if event.get("exam_type") == "cbt"
            for alloc in event["venues"]
        ),
        "maximum_exams_per_student_per_week": diagnostics.get("student_workload", {}).get(
            "maximum_exams_per_student_per_week", 0
        ),
        "students_over_three_exams_per_week": diagnostics.get("student_workload", {}).get(
            "students_over_three_exams_per_week", 0
        ),
        "average_exams_per_student_week": diagnostics.get("student_workload", {}).get(
            "average_exams_per_student_week", 0.0
        ),
        "maximum_exams_per_student_per_day": diagnostics.get("student_workload", {}).get(
            "maximum_exams_per_student_per_day", 0
        ),
        "runtime_seconds": elapsed,
        "result_status": "feasible" if not unscheduled else "best_available",
    }

    return ExamGenerationResult(
        status=status,
        events=events,
        diagnostics=diagnostics,
        metrics=metrics,
        fitness=quality_score,
        evaluation=evaluation,
        conflict_report=conflict_report,
        runtime_seconds=elapsed,
        problem=problem,
    )

