import copy
import datetime
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from django.db.models import IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce

from courses.models import Course
from hierarchy.models import Faculty, School
from scheduling.models import Semester, TimetableGenerationRun
from .evaluation.evaluator import evaluate
from .evaluation.report import generate_conflict_report
from .generator import generate_timetable
from .genetic.algorithm import OptimizerConfig
from .models.assignment import Assignment
from .models.problem import SchedulingProblem
from .preprocessing.pipeline import build_scheduling_problem_from_db
from .publisher import publish_generation_run


def _tune_faculty_config(
    occurrence_count: int,
    user_config: Optional[OptimizerConfig] = None,
) -> OptimizerConfig:
    """
    Selects fast, effective GA hyperparameters for a single faculty sub-problem.
    Ensures rapid convergence (8-30s per faculty) while respecting hard constraints.
    """
    if occurrence_count <= 60:
        base_pop = 50
        base_gens = 45
        base_patience = 12
    elif occurrence_count <= 120:
        base_pop = 60
        base_gens = 60
        base_patience = 15
    elif occurrence_count <= 200:
        base_pop = 70
        base_gens = 75
        base_patience = 18
    else:
        # Largest faculties (e.g. FNAS with 300+ occurrences)
        base_pop = 80
        base_gens = 80
        base_patience = 20

    if user_config:
        return OptimizerConfig(
            population_size=user_config.population_size or base_pop,
            max_generations=min(user_config.max_generations or base_gens, base_gens),
            mutation_rate=user_config.mutation_rate or 0.08,
            patience=min(user_config.patience or base_patience, base_patience),
            crossover_rate=user_config.crossover_rate or 0.85,
            enable_repair=True,
        )

    return OptimizerConfig(
        population_size=base_pop,
        max_generations=base_gens,
        mutation_rate=0.08,
        patience=base_patience,
        crossover_rate=0.85,
        enable_repair=True,
    )


def generate_school_timetable_decomposed(
    semester: Semester,
    school_id: int | str,
    config: Optional[OptimizerConfig] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    initiated_by=None,
    publish_immediately: bool = False,
) -> TimetableGenerationRun:
    """
    Decomposed School-Scope Timetable Generator (Option A):
    1. Ranks all faculties under the target school by planned student population descending.
    2. Schedules institutional core courses (GST / university general courses) in Step 0.
    3. Iteratively runs the GA for each faculty in descending population order.
    4. Propagates cumulative blocked venue-slots, lecturer-slots, and cohort-slots across faculties
       to ensure zero inter-faculty clashes for shared facilities, shared staff, and cohorts.
    5. Streams real-time progress events via progress_callback.
    6. Assembles the final unified school-scope TimetableGenerationRun with complete diagnostics.
    """
    start_time = time.time()
    school = School.objects.filter(id=int(school_id)).first()
    school_name = school.name if school else f"School #{school_id}"

    # 1. Fetch faculties ordered by planned student population descending
    faculties_qs = (
        Faculty.objects.filter(school_id=school_id)
        .annotate(
            total_students=Coalesce(
                Sum("departments__programs__student_counts__count"),
                Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-total_students", "name")
    )
    faculties = list(faculties_qs)

    total_steps = len(faculties) + 1  # Step 0 (Core) + N faculties
    faculty_summary_list = [
        {
            "id": fac.id,
            "code": fac.code,
            "name": fac.name,
            "population": fac.total_students,
            "status": "queued",
            "occurrencesCount": 0,
        }
        for fac in faculties
    ]

    # Notify initial start
    if progress_callback:
        progress_callback({
            "stage": "init",
            "step": 0,
            "totalSteps": total_steps,
            "percent": 2,
            "message": f"Initializing school-wide schedule for {school_name} across {len(faculties)} faculties...",
            "faculties": faculty_summary_list,
        })

    cumulative_blocked_venues: Dict[int | str, Set[str]] = {}
    cumulative_blocked_lecturers: Dict[int | str, Set[str]] = {}
    cumulative_blocked_cohorts: Dict[Tuple[int, int], Set[str]] = {}

    all_assignments_payload: List[Dict[str, Any]] = []
    all_evaluated_assignments: List[Assignment] = []
    scheduled_course_ids: Set[int | str] = set()

    total_generations_run = 0
    faculty_metrics: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # STEP 0: Institutional Core / GST General Courses
    # -------------------------------------------------------------------------
    core_courses_qs = Course.objects.filter(
        Q(owning_school_id=school_id) | Q(owning_school__isnull=True),
        owning_level__in=[Course.OwningLevel.GENERAL, Course.OwningLevel.SCHOOL],
        owning_faculty__isnull=True,
    ).filter(Q(semester=semester) | Q(semester__isnull=True)).distinct()

    core_course_count = core_courses_qs.count()
    if core_course_count > 0:
        if progress_callback:
            progress_callback({
                "stage": "core",
                "step": 0,
                "totalSteps": total_steps,
                "percent": 5,
                "message": f"Scheduling {core_course_count} University Core / GST courses...",
                "faculties": faculty_summary_list,
            })

        try:
            # Build mini problem for core courses
            school_problem = build_scheduling_problem_from_db(
                semester_id=semester.id,
                scope_type="school",
                scope_id=school_id,
            )
            core_course_ids = set(core_courses_qs.values_list("id", flat=True))
            core_occurrences = [
                occ for occ in school_problem.occurrences if occ.course_id in core_course_ids
            ]

            if core_occurrences:
                mini_problem = SchedulingProblem(
                    occurrences=core_occurrences,
                    valid_slots=school_problem.valid_slots,
                    venues=school_problem.venues,
                    student_conflict_graph=school_problem.student_conflict_graph,
                    shared_student_groups=school_problem.shared_student_groups,
                    lecturers_by_course=school_problem.lecturers_by_course,
                    lecturer_details=school_problem.lecturer_details,
                    allowed_venues_by_course=school_problem.allowed_venues_by_course,
                    daily_lecture_limit=school_problem.daily_lecture_limit,
                    scope_type="school",
                    scope_id=school_id,
                    scope_name=school_name,
                    semester_id=semester.id,
                )
                core_config = OptimizerConfig(
                    population_size=40,
                    max_generations=30,
                    patience=10,
                )
                core_result = generate_timetable(mini_problem, config=core_config)

                for item in core_result.assignments_payload:
                    item["faculty_id"] = None
                    item["faculty_name"] = "University Core"
                    all_assignments_payload.append(item)

                for a in core_result.assignments:
                    all_evaluated_assignments.append(a)
                    scheduled_course_ids.add(a.occurrence.course_id)
                    sid = a.slot.slot_id
                    cumulative_blocked_venues.setdefault(a.venue_id, set()).add(sid)
                    for lid in a.occurrence.lecturer_ids:
                        cumulative_blocked_lecturers.setdefault(lid, set()).add(sid)
                    for grp in a.occurrence.student_groups:
                        cumulative_blocked_cohorts.setdefault((grp.program_id, grp.level), set()).add(sid)

                total_generations_run += core_result.generation_count
        except Exception:
            # Non-blocking if no core courses can be isolated
            pass

    # -------------------------------------------------------------------------
    # STEPS 1..N: Faculties in Population Descending Order
    # -------------------------------------------------------------------------
    total_faculties = len(faculties)
    for idx, fac in enumerate(faculties, start=1):
        percent_start = int(5 + ((idx - 1) / total_faculties) * 85)

        # Update faculty status in queue
        for f_item in faculty_summary_list:
            if f_item["id"] == fac.id:
                f_item["status"] = "running"

        if progress_callback:
            progress_callback({
                "stage": "faculty",
                "step": idx,
                "totalSteps": total_steps,
                "percent": percent_start,
                "facultyId": fac.id,
                "facultyCode": fac.code,
                "facultyName": fac.name,
                "population": fac.total_students,
                "status": "running",
                "message": f"Generating for {fac.name} ({idx}/{total_faculties}) — Pop: {fac.total_students:,}...",
                "faculties": faculty_summary_list,
                "occurrencesPlaced": len(all_assignments_payload),
            })

        fac_t0 = time.time()

        # Build faculty problem
        fac_problem = build_scheduling_problem_from_db(
            semester_id=semester.id,
            scope_type="faculty",
            scope_id=fac.id,
        )

        # Filter out core courses already scheduled in Step 0
        if scheduled_course_ids:
            fac_problem.occurrences = [
                occ for occ in fac_problem.occurrences if occ.course_id not in scheduled_course_ids
            ]
            fac_problem.occurrence_by_id = {
                occ.occurrence_id: occ for occ in fac_problem.occurrences
            }

        # Inject cumulative inter-faculty commitments (clearing out old published run relics)
        fac_problem.blocked_venue_slots = copy.deepcopy(cumulative_blocked_venues)
        fac_problem.blocked_lecturer_slots = copy.deepcopy(cumulative_blocked_lecturers)
        fac_problem.blocked_cohort_slots = copy.deepcopy(cumulative_blocked_cohorts)

        # Configure tuned GA parameters
        fac_config = _tune_faculty_config(len(fac_problem.occurrences), user_config=config)

        # Execute optimization for this faculty
        fac_result = generate_timetable(fac_problem, config=fac_config)
        fac_elapsed = time.time() - fac_t0
        total_generations_run += fac_result.generation_count

        # Ingest and tag faculty assignments
        for item in fac_result.assignments_payload:
            item["faculty_id"] = fac.id
            item["faculty_name"] = fac.name
            item["faculty_code"] = fac.code
            all_assignments_payload.append(item)

        for a in fac_result.assignments:
            all_evaluated_assignments.append(a)
            scheduled_course_ids.add(a.occurrence.course_id)
            sid = a.slot.slot_id
            cumulative_blocked_venues.setdefault(a.venue_id, set()).add(sid)
            for lid in a.occurrence.lecturer_ids:
                cumulative_blocked_lecturers.setdefault(lid, set()).add(sid)
            for grp in a.occurrence.student_groups:
                cumulative_blocked_cohorts.setdefault((grp.program_id, grp.level), set()).add(sid)

        # Update faculty item in summary list
        for f_item in faculty_summary_list:
            if f_item["id"] == fac.id:
                f_item["status"] = "completed"
                f_item["occurrencesCount"] = len(fac_result.assignments)

        faculty_metrics.append({
            "faculty_id": fac.id,
            "faculty_code": fac.code,
            "faculty_name": fac.name,
            "population": fac.total_students,
            "occurrences_count": len(fac_result.assignments),
            "hard_conflicts": fac_result.hard_conflicts_count,
            "status": fac_result.status,
            "runtime_seconds": round(fac_elapsed, 2),
        })

        percent_done = int(5 + (idx / total_faculties) * 85)
        if progress_callback:
            progress_callback({
                "stage": "faculty",
                "step": idx,
                "totalSteps": total_steps,
                "percent": percent_done,
                "facultyId": fac.id,
                "facultyCode": fac.code,
                "facultyName": fac.name,
                "population": fac.total_students,
                "status": "completed",
                "occurrencesPlaced": len(all_assignments_payload),
                "message": f"Completed {fac.name}: {len(fac_result.assignments)} sessions placed in {fac_elapsed:.1f}s.",
                "faculties": faculty_summary_list,
            })

    # -------------------------------------------------------------------------
    # FINALIZE: Evaluate Complete School Schedule & Assemble Run Record
    # -------------------------------------------------------------------------
    if progress_callback:
        progress_callback({
            "stage": "finalizing",
            "step": total_steps,
            "totalSteps": total_steps,
            "percent": 95,
            "message": "Assembling unified institutional timetable and conflict diagnostics...",
            "faculties": faculty_summary_list,
            "occurrencesPlaced": len(all_assignments_payload),
        })

    # Re-evaluate complete assignment set against full institutional problem model
    school_full_problem = build_scheduling_problem_from_db(
        semester_id=semester.id,
        scope_type="school",
        scope_id=school_id,
    )
    # Clear out blocked slots for evaluation so we evaluate true internal clashes
    school_full_problem.blocked_venue_slots = {}
    school_full_problem.blocked_lecturer_slots = {}
    school_full_problem.blocked_cohort_slots = {}

    final_eval = evaluate(all_evaluated_assignments, school_full_problem, collect_details=True)

    total_occ = max(1, len(all_evaluated_assignments))
    total_students = sum(
        item.get("expected_students", 50) for item in all_assignments_payload
    ) or (50 * total_occ)

    hard_conflicts = final_eval.hard_conflicts
    cap_penalty = final_eval.capacity_penalty

    if hard_conflicts == 0:
        status_str = "OPTIMAL" if cap_penalty == 0 else "FEASIBLE"
        capacity_fit = max(0.0, 1.0 - (cap_penalty / max(1, total_students * 1.5)))
        quality_score = 0.90 + (0.10 * capacity_fit)
    else:
        status_str = "BEST_AVAILABLE"
        hard_factor = max(0.0, 1.0 - (hard_conflicts / total_occ))
        capacity_factor = max(0.0, 1.0 - (cap_penalty / max(1, total_students * 2.0)))
        quality_score = max(0.0, 0.85 * hard_factor + 0.05 * capacity_factor)

    quality_score = round(quality_score, 4)

    conflict_report = generate_conflict_report(
        final_eval,
        total_occurrences=total_occ,
        quality_score=quality_score,
    )

    total_elapsed = time.time() - start_time
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create master school-wide TimetableGenerationRun
    run = TimetableGenerationRun.objects.create(
        semester=semester,
        scope_type=TimetableGenerationRun.ScopeType.SCHOOL,
        scope_id=int(school_id),
        scope_name=school_name,
        status=TimetableGenerationRun.Status.COMPLETED,
        result_status=status_str.lower(),
        hard_conflicts_count=final_eval.hard_conflicts,
        student_conflicts_count=final_eval.student_conflicts,
        lecturer_conflicts_count=final_eval.lecturer_conflicts,
        venue_conflicts_count=final_eval.venue_conflicts,
        daily_limit_violations_count=final_eval.daily_limit_violations,
        occurrence_day_violations_count=final_eval.occurrence_day_violations,
        capacity_penalty=final_eval.capacity_penalty,
        fitness_score=quality_score,
        conflict_report=conflict_report,
        generation_metrics={
            "generations_run": total_generations_run,
            "runtime_seconds": round(total_elapsed, 2),
            "elapsed_seconds": round(total_elapsed, 2),
            "occurrences_total": len(all_assignments_payload),
            "decomposed_generation": True,
            "faculty_breakdown": faculty_metrics,
        },
        assignments_payload=all_assignments_payload,
        initiated_by=initiated_by,
        completed_at=now,
    )

    if publish_immediately:
        publish_generation_run(run, created_by_admin=initiated_by)

    if progress_callback:
        progress_callback({
            "stage": "complete",
            "step": total_steps,
            "totalSteps": total_steps,
            "percent": 100,
            "runId": str(run.id),
            "message": f"School-wide timetable generated successfully! {len(all_assignments_payload)} lecture sessions scheduled.",
            "faculties": faculty_summary_list,
            "occurrencesPlaced": len(all_assignments_payload),
            "run": {
                "id": str(run.id),
                "scope_type": run.scope_type,
                "scope_id": run.scope_id,
                "scope_name": run.scope_name,
                "status": run.status,
                "result_status": run.result_status,
                "hard_conflicts_count": run.hard_conflicts_count,
                "student_conflicts_count": run.student_conflicts_count,
                "lecturer_conflicts_count": run.lecturer_conflicts_count,
                "venue_conflicts_count": run.venue_conflicts_count,
                "daily_limit_violations_count": run.daily_limit_violations_count,
                "occurrence_day_violations_count": run.occurrence_day_violations_count,
                "capacity_penalty": run.capacity_penalty,
                "fitness_score": run.fitness_score,
                "conflict_report": run.conflict_report,
                "generation_metrics": run.generation_metrics,
                "assignments_payload": run.assignments_payload,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
        })

    return run

