"""Student course registration and exact student conflict graph precomputation."""

from typing import Dict, List, Set, Tuple

from courses.models import Course, CourseRegistration
from scheduling.models import Semester


def build_exam_conflict_graph(
    courses: List[Course],
    semester: Semester,
) -> Tuple[
    Dict[int, Set[int | str]],
    Dict[int, Set[int]],
    Dict[Tuple[int, int], float],
]:
    """Precomputes exact student registrations, the hard conflict graph, and cohort overlap ratios.

    Two courses conflict if and only if they share at least one registered student:
        Conflict(A, B) = 1 iff Students(A) ∩ Students(B) ≠ ∅

    Returns:
        (students_by_course, student_conflict_graph, cohort_overlaps)
    """
    course_ids = [c.id for c in courses]
    session_label = semester.session.label if hasattr(semester, "session") and semester.session else ""

    registrations = CourseRegistration.objects.filter(
        course_id__in=course_ids,
        academic_session=session_label,
    ).values_list("course_id", "student_id")

    students_by_course: Dict[int, Set[int | str]] = {cid: set() for cid in course_ids}
    for course_id, student_id in registrations:
        students_by_course.setdefault(course_id, set()).add(student_id)

    student_conflict_graph: Dict[int, Set[int]] = {cid: set() for cid in course_ids}
    cohort_overlaps: Dict[Tuple[int, int], float] = {}

    course_list = list(courses)
    from courses.services import get_course_attributed_programs, calculate_course_student_count
    from student_counts.models import ProgramStudentCount

    program_counts = {
        (psc.program_id, psc.level): psc.count
        for psc in ProgramStudentCount.objects.all()
    }

    # For courses lacking explicit student registration rows, synthesize deterministic cohort student IDs
    for course in courses:
        if not students_by_course[course.id]:
            attributed_pids = get_course_attributed_programs(course)
            synth_students = set()
            if attributed_pids:
                for pid in sorted(attributed_pids):
                    headcount = program_counts.get((pid, course.level), 0)
                    for k in range(1, headcount + 1):
                        synth_students.add(f"cohort_p{pid}_l{course.level}_{k}")
            if not synth_students:
                est = calculate_course_student_count(course)
                for k in range(1, est + 1):
                    synth_students.add(f"cohort_c{course.id}_{k}")
            students_by_course[course.id] = synth_students

    # Precompute attributed program cohorts per course: (program_id, course.level)
    course_cohorts = {
        c.id: {(pid, c.level) for pid in get_course_attributed_programs(c)}
        for c in courses
    }

    for i, course_a in enumerate(course_list):
        students_a = students_by_course.get(course_a.id, set())
        cohorts_a = course_cohorts.get(course_a.id, set())

        for j in range(i + 1, len(course_list)):
            course_b = course_list[j]
            students_b = students_by_course.get(course_b.id, set())
            cohorts_b = course_cohorts.get(course_b.id, set())

            intersection_students = students_a.intersection(students_b) if (students_a and students_b) else set()
            intersection_cohorts = cohorts_a.intersection(cohorts_b) if (cohorts_a and cohorts_b) else set()

            if intersection_students:
                student_conflict_graph[course_a.id].add(course_b.id)
                student_conflict_graph[course_b.id].add(course_a.id)

                union_len = len(students_a.union(students_b))
                jaccard = round(len(intersection_students) / union_len, 4) if union_len > 0 else 0.0
                cohort_overlaps[(course_a.id, course_b.id)] = jaccard
                cohort_overlaps[(course_b.id, course_a.id)] = jaccard
            elif intersection_cohorts:
                student_conflict_graph[course_a.id].add(course_b.id)
                student_conflict_graph[course_b.id].add(course_a.id)

                union_cohorts_len = len(cohorts_a.union(cohorts_b))
                jaccard = round(len(intersection_cohorts) / union_cohorts_len, 4) if union_cohorts_len > 0 else 0.0
                cohort_overlaps[(course_a.id, course_b.id)] = jaccard
                cohort_overlaps[(course_b.id, course_a.id)] = jaccard

    return students_by_course, student_conflict_graph, cohort_overlaps

