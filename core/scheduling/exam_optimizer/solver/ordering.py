"""Difficulty ordering heuristic for constructive examination placement."""

from typing import List
from ..models.event import ExamEvent


def compute_exam_difficulty(event: ExamEvent) -> float:
    """Computes a composite difficulty score to prioritize placement of heavily constrained exams:

    Difficulty(E) = w1 * Population + w2 * ConflictDegree + w3 * Duration + w4 * VenueScarcity
    """
    return (
        1.0 * event.student_count
        + 20.0 * event.conflict_degree
        + 0.5 * event.duration_minutes
        + 50.0 * event.venue_scarcity
    )


def order_exam_events(events: List[ExamEvent]) -> List[ExamEvent]:
    """Orders exam events from most constrained to least constrained."""
    return sorted(
        events,
        key=lambda e: (-compute_exam_difficulty(e), -e.student_count, e.course_code),
    )

