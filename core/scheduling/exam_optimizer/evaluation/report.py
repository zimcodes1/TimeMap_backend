"""Conflict report generation for the exam scheduler."""

from typing import Any, Dict, Optional
from .evaluator import ExamEvaluationResult


def generate_exam_conflict_report(
    evaluation: ExamEvaluationResult,
    total_events: int,
    quality_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Builds a structured, human-readable conflict diagnostics report for administrator inspection."""
    status_label = (
        "OPTIMAL"
        if evaluation.is_optimal
        else ("FEASIBLE" if evaluation.is_feasible else "BEST_AVAILABLE")
    )

    effective_quality = (
        quality_score if quality_score is not None else round(evaluation.fitness, 4)
    )

    student_conflicts = [
        d for d in evaluation.conflict_details if "Student conflict" in d.get("reason", "")
    ]
    venue_conflicts = [
        d for d in evaluation.conflict_details if "Venue conflict" in d.get("reason", "")
    ]
    calendar_violations = [
        d
        for d in evaluation.conflict_details
        if "calendar" in d.get("reason", "").lower() or "period" in d.get("reason", "").lower()
    ]
    capacity_violations = [
        d
        for d in evaluation.conflict_details
        if "capacity" in d.get("reason", "").lower() or "population" in d.get("reason", "").lower()
    ]

    return {
        "status": status_label,
        "is_feasible": evaluation.is_feasible,
        "events_scheduled": total_events,
        "hard_conflicts_total": evaluation.hard_conflicts,
        "summary": {
            "student_conflicts": evaluation.student_conflicts,
            "venue_conflicts": evaluation.venue_conflicts,
            "calendar_violations": evaluation.calendar_violations,
            "capacity_violations": evaluation.capacity_violations,
            "workload_penalty": round(evaluation.workload_penalty, 2),
            "quality_score": round(effective_quality, 4),
            "quality_percentage": round(effective_quality * 100, 1),
            "raw_fitness": round(evaluation.fitness, 6),
        },
        "details": {
            "student_conflicts": student_conflicts,
            "venue_conflicts": venue_conflicts,
            "calendar_violations": calendar_violations,
            "capacity_violations": capacity_violations,
        },
    }

