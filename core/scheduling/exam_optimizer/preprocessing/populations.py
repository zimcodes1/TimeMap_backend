"""Course population aggregation and logical exam event construction."""

from typing import Dict, List, Set
from courses.models import Course
from courses.services import calculate_course_student_count, get_course_attributed_programs
from hierarchy.models import Program
from student_counts.models import ProgramStudentCount

from ..models.event import ExamEvent, ExamPopulation
from .durations import resolve_exam_durations


def resolve_course_populations(
    courses: List[Course],
    students_by_course: Dict[int, Set[int | str]],
    conflict_graph: Dict[int, Set[int]],
) -> Dict[int, ExamEvent]:
    """Constructs normalized logical ExamEvent objects from course data.

    Calculates effective student counts across all originating and granted program cohorts,
    taking the maximum of explicit student registrations and cohort headcount estimates.
    """
    events: Dict[int, ExamEvent] = {}

    programs_map = {
        p.id: p for p in Program.objects.select_related("department").all()
    }
    program_counts = {
        (psc.program_id, psc.level): psc.count
        for psc in ProgramStudentCount.objects.all()
    }

    for course in courses:
        registered_students = students_by_course.get(course.id, set())
        estimated_count = calculate_course_student_count(course)

        exam_type = course.exam_type or Course.ExamType.WRITTEN
        duration, per_student = resolve_exam_durations(course, exam_type)

        # Attribute populations across all eligible program cohorts
        attributed_pids = get_course_attributed_programs(course)
        populations: List[ExamPopulation] = []

        if attributed_pids:
            for pid in sorted(attributed_pids):
                p = programs_map.get(pid)
                headcount = program_counts.get((pid, course.level), 0)
                if headcount > 0:
                    pop_students = {f"cohort_p{pid}_l{course.level}_{k}" for k in range(1, headcount + 1)}
                    populations.append(
                        ExamPopulation(
                            course_id=course.id,
                            department_id=p.department_id if p else None,
                            department_name=p.department.name if p and p.department else None,
                            program_id=pid,
                            program_name=p.name if p else None,
                            level=course.level,
                            student_count=headcount,
                            student_ids=pop_students,
                        )
                    )

        total_cohort_headcount = sum(p.student_count for p in populations)
        effective_count = max(len(registered_students), total_cohort_headcount, estimated_count)

        if not registered_students and populations:
            registered_students = set()
            for pop in populations:
                registered_students.update(pop.student_ids)
        elif not registered_students:
            registered_students = {f"cohort_c{course.id}_{k}" for k in range(1, effective_count + 1)}

        department = course.owning_department or (
            course.target_program.department if course.target_program_id else None
        )

        dept_id = department.id if department else None
        dept_name = department.name if department else (
            f"{course.owning_faculty.name} (General)" if course.owning_faculty else "General Studies"
        )
        prog_id = course.target_program_id
        prog_name = course.target_program.name if course.target_program_id else (
            "Faculty Core" if course.owning_faculty else "General Core"
        )

        if not populations:
            populations.append(
                ExamPopulation(
                    course_id=course.id,
                    department_id=dept_id,
                    department_name=dept_name,
                    program_id=prog_id,
                    program_name=prog_name,
                    level=course.level,
                    student_count=effective_count,
                    student_ids=registered_students,
                )
            )

        conflict_deg = len(conflict_graph.get(course.id, set()))

        event = ExamEvent(
            course_id=course.id,
            course_code=course.code,
            course_title=course.title,
            course_level=course.level,
            exam_type=exam_type,
            duration_minutes=duration,
            duration_per_student_minutes=per_student,
            student_count=effective_count,
            student_ids=registered_students,
            populations=populations,
            attributed_program_ids=set(attributed_pids),
            department_id=dept_id,
            department_name=dept_name,
            program_id=prog_id,
            program_name=prog_name,
            conflict_degree=conflict_deg,
            venue_scarcity=0.0,
        )
        events[course.id] = event

    return events

