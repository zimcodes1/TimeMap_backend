from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..constraints.capacity import calculate_capacity_penalty
from ..constraints.daily_limits import check_daily_limits
from ..constraints.lecturers import check_lecturer_conflicts
from ..constraints.occurrences import check_occurrence_days
from ..constraints.students import check_student_conflicts
from ..constraints.venues import check_venue_conflicts
from ..models.assignment import Assignment
from ..models.problem import SchedulingProblem

# Constraint Penalty Weights (Higher = more severe)
WEIGHT_STUDENT_CONFLICT = 10000
WEIGHT_LECTURER_CONFLICT = 5000
WEIGHT_VENUE_CONFLICT = 5000
WEIGHT_OCCURRENCE_DAY = 5000
WEIGHT_DAILY_LIMIT = 2000
WEIGHT_CAPACITY_OVERFLOW = 1


@dataclass
class EvaluationResult:
    """
    Detailed evaluation outcome for a candidate timetable chromosome.
    """

    student_conflicts: int
    lecturer_conflicts: int
    venue_conflicts: int
    daily_limit_violations: int
    occurrence_day_violations: int
    capacity_penalty: int

    total_weighted_penalty: float
    fitness: float

    # Detailed list of diagnostic violation items
    conflict_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def hard_conflicts(self) -> int:
        return (
            self.student_conflicts
            + self.lecturer_conflicts
            + self.venue_conflicts
            + self.daily_limit_violations
            + self.occurrence_day_violations
        )

    @property
    def is_feasible(self) -> bool:
        return self.hard_conflicts == 0

    @property
    def is_optimal(self) -> bool:
        return self.hard_conflicts == 0 and self.capacity_penalty == 0

    @property
    def lexicographic_rank(self) -> Tuple[int, int, int, int, int, int]:
        """
        Prioritized comparison tuple:
        Lower tuple values represent superior candidates.
        """
        return (
            self.student_conflicts,
            self.lecturer_conflicts,
            self.venue_conflicts,
            self.occurrence_day_violations,
            self.daily_limit_violations,
            self.capacity_penalty,
        )


def evaluate(
    assignments: List[Assignment],
    problem: SchedulingProblem,
    collect_details: bool = False,
) -> EvaluationResult:
    """
    Evaluates a candidate schedule against all 6 constraint handlers.
    Calculates independent counters, weighted penalty, lexicographic tuple, and fitness.
    """
    # 1. Student clashes (hardest / highest priority)
    stu_count, stu_details = check_student_conflicts(assignments, problem)

    # 2. Lecturer double-booking (hard)
    lec_count, lec_details = check_lecturer_conflicts(assignments, problem)

    # 3. Venue double-booking (hard)
    ven_count, ven_details = check_venue_conflicts(assignments, problem)

    # 4. Daily limits per cohort (hard, max 3/day)
    day_lim_count, day_lim_details = check_daily_limits(assignments, problem)

    # 5. Repeated occurrence separation (hard, distinct days)
    occ_day_count, occ_day_details = check_occurrence_days(assignments, problem)

    # 6. Venue capacity (soft)
    cap_penalty, cap_details = calculate_capacity_penalty(assignments, problem)

    # Calculate weighted penalty
    total_penalty = (
        stu_count * WEIGHT_STUDENT_CONFLICT
        + lec_count * WEIGHT_LECTURER_CONFLICT
        + ven_count * WEIGHT_VENUE_CONFLICT
        + occ_day_count * WEIGHT_OCCURRENCE_DAY
        + day_lim_count * WEIGHT_DAILY_LIMIT
        + cap_penalty * WEIGHT_CAPACITY_OVERFLOW
    )

    # Fitness score in range (0, 1]
    fitness = 1.0 / (1.0 + total_penalty)

    all_details: List[Dict[str, Any]] = []
    if collect_details:
        all_details.extend(stu_details)
        all_details.extend(lec_details)
        all_details.extend(ven_details)
        all_details.extend(occ_day_details)
        all_details.extend(day_lim_details)
        all_details.extend(cap_details)

    return EvaluationResult(
        student_conflicts=stu_count,
        lecturer_conflicts=lec_count,
        venue_conflicts=ven_count,
        daily_limit_violations=day_lim_count,
        occurrence_day_violations=occ_day_count,
        capacity_penalty=cap_penalty,
        total_weighted_penalty=total_penalty,
        fitness=fitness,
        conflict_details=all_details,
    )

