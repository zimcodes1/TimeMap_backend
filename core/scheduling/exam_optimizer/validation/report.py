"""Diagnostic metrics and workload reporting for the exam optimizer."""

from typing import Any, Dict, List

from ..constraints.workload import calculate_student_workload


def build_exam_diagnostics(
    events: List[Dict[str, Any]],
    unscheduled: List[Dict[str, Any]],
    scheduled_states: List[Dict[str, Any]],
    validation_result: Dict[str, Any],
    candidate_windows_evaluated: int,
    joined_sessions_count: int,
) -> Dict[str, Any]:
    """Compiles the complete diagnostics dictionary matching API and audit contracts."""
    raw_workload = calculate_student_workload(scheduled_states)

    workload_summary = {
        "maximum_exams_per_student_per_week": raw_workload.get(
            "maximum_exams_per_student_per_week", 0
        ),
        "students_over_three_exams_per_week": raw_workload.get(
            "students_over_three_exams_per_week", 0
        ),
        "average_exams_per_student_week": raw_workload.get(
            "average_exams_per_student_week", 0.0
        ),
        "maximum_exams_per_student_per_day": raw_workload.get(
            "maximum_exams_per_student_per_day", 0
        ),
    }

    with_reg = sum(bool(s["student_ids"]) for s in scheduled_states)
    with_est = len(events) - with_reg

    return {
        "scheduled": len(events),
        "unscheduled": unscheduled,
        "joined_sessions": joined_sessions_count,
        "validation": validation_result,
        "candidate_windows_evaluated": candidate_windows_evaluated,
        "population_data": {
            "events_with_registration_membership": with_reg,
            "events_using_population_estimates": with_est,
        },
        "student_workload": workload_summary,
    }

