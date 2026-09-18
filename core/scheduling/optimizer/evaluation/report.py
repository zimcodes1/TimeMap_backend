from typing import Any, Dict

from .evaluator import EvaluationResult


def generate_conflict_report(
    evaluation: EvaluationResult,
    total_occurrences: int,
    quality_score: float | None = None,
) -> Dict[str, Any]:
    """
    Builds a comprehensive, human-readable conflict diagnostics report
    ready for JSON serialization and administrator dashboard inspection.
    """
    status_label = "OPTIMAL" if evaluation.is_optimal else ("FEASIBLE" if evaluation.is_feasible else "BEST_AVAILABLE")

    # Group conflict details by category
    student_conflicts = [d for d in evaluation.conflict_details if d.get("type") == "student_conflict"]
    lecturer_conflicts = [d for d in evaluation.conflict_details if d.get("type") == "lecturer_conflict"]
    venue_conflicts = [d for d in evaluation.conflict_details if d.get("type") == "venue_conflict"]
    daily_limit_violations = [d for d in evaluation.conflict_details if d.get("type") == "daily_limit_violation"]
    occurrence_day_violations = [d for d in evaluation.conflict_details if d.get("type") == "occurrence_day_violation"]
    capacity_overflows = [d for d in evaluation.conflict_details if d.get("type") == "capacity_overflow"]

    effective_quality = quality_score if quality_score is not None else round(evaluation.fitness, 4)

    return {
        "status": status_label,
        "is_feasible": evaluation.is_feasible,
        "occurrences_scheduled": total_occurrences,
        "hard_conflicts_total": evaluation.hard_conflicts,
        "summary": {
            "student_conflicts": evaluation.student_conflicts,
            "lecturer_conflicts": evaluation.lecturer_conflicts,
            "venue_conflicts": evaluation.venue_conflicts,
            "daily_limit_violations": evaluation.daily_limit_violations,
            "occurrence_day_violations": evaluation.occurrence_day_violations,
            "capacity_penalty": evaluation.capacity_penalty,
            "fitness_score": round(effective_quality, 4),
            "quality_percentage": round(effective_quality * 100, 1),
            "raw_fitness": round(evaluation.fitness, 6),
        },
        "details": {
            "student_conflicts": student_conflicts,
            "lecturer_conflicts": lecturer_conflicts,
            "venue_conflicts": venue_conflicts,
            "daily_limit_violations": daily_limit_violations,
            "occurrence_day_violations": occurrence_day_violations,
            "capacity_overflows": capacity_overflows,
            "capacity_violations": capacity_overflows,
        },
        "student_conflicts": student_conflicts,
        "lecturer_conflicts": lecturer_conflicts,
        "venue_conflicts": venue_conflicts,
        "daily_limit_violations": daily_limit_violations,
        "occurrence_day_violations": occurrence_day_violations,
        "capacity_overflows": capacity_overflows,
        "capacity_violations": capacity_overflows,
    }

