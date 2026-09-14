from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .evaluation.evaluator import EvaluationResult
from .evaluation.report import generate_conflict_report
from .genetic.algorithm import OptimizerConfig, run_genetic_algorithm
from .models.assignment import Assignment
from .models.problem import SchedulingProblem


@dataclass
class GenerationResult:
    """
    Standard generation result produced by the optimizer engine.
    """

    status: str  # "OPTIMAL", "FEASIBLE", "BEST_AVAILABLE", "FAILED"
    assignments: List[Assignment]
    fitness: float
    evaluation: EvaluationResult
    conflict_report: Dict[str, Any]
    generation_count: int
    runtime_seconds: float
    assignments_payload: List[Dict[str, Any]]

    @property
    def is_feasible(self) -> bool:
        return self.evaluation.is_feasible

    @property
    def hard_conflicts_count(self) -> int:
        return self.evaluation.hard_conflicts


def generate_timetable(
    problem: SchedulingProblem,
    config: Optional[OptimizerConfig] = None,
    progress_callback: Optional[Callable[[int, int, EvaluationResult], None]] = None,
) -> GenerationResult:
    """
    High-level facade function to run the GA timetable optimizer.
    Receives a pure SchedulingProblem, executes the evolutionary search,
    validates the best chromosome, and returns a comprehensive GenerationResult.
    """
    best_chrome, final_eval, gens_run, elapsed = run_genetic_algorithm(
        problem,
        config=config,
        progress_callback=progress_callback,
    )

    # Determine status
    if final_eval.is_optimal:
        status = "OPTIMAL"
    elif final_eval.is_feasible:
        status = "FEASIBLE"
    elif problem.total_occurrences == 0:
        status = "FEASIBLE"
    else:
        status = "BEST_AVAILABLE"

    # Build conflict diagnostics report
    conflict_report = generate_conflict_report(
        final_eval,
        total_occurrences=problem.total_occurrences,
    )

    # Build serializable assignments payload
    assignments_payload: List[Dict[str, Any]] = []
    for a in best_chrome.assignments:
        venue = problem.venues.get(a.venue_id)
        venue_name = venue.name if venue else f"Venue #{a.venue_id}"

        assignments_payload.append(
            {
                "occurrence_id": a.occurrence.occurrence_id,
                "course_id": a.occurrence.course_id,
                "course_code": a.occurrence.course_code,
                "course_title": a.occurrence.course_title,
                "occurrence_index": a.occurrence.occurrence_index,
                "course_type": a.occurrence.course_type,
                "day": a.slot.day,
                "day_name": a.slot.day_name,
                "period_index": a.slot.period_index,
                "start_time": a.slot.start_time,
                "end_time": a.slot.end_time,
                "venue_id": a.venue_id,
                "venue_name": venue_name,
                "expected_students": a.occurrence.expected_students,
            }
        )

    return GenerationResult(
        status=status,
        assignments=best_chrome.assignments,
        fitness=final_eval.fitness,
        evaluation=final_eval,
        conflict_report=conflict_report,
        generation_count=gens_run,
        runtime_seconds=round(elapsed, 3),
        assignments_payload=assignments_payload,
    )

