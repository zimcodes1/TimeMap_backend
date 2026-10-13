"""Modular examination timetable optimizer package."""

from .allocation.planner import allocate_venues as _allocate
from .generator import ExamGenerationResult, generate_exam_timetable
from .models.problem import ExamSchedulingProblem
from .preprocessing.calendar import date_windows as _date_windows
from .preprocessing.calendar import is_within_policy as _within_policy
from .preprocessing.pipeline import build_exam_problem_from_db

__all__ = [
    "generate_exam_timetable",
    "ExamGenerationResult",
    "ExamSchedulingProblem",
    "build_exam_problem_from_db",
    "_allocate",
    "_date_windows",
    "_within_policy",
]

