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
    for i, course_a in enumerate(course_list):
        students_a = students_by_course.get(course_a.id, set())
        if not students_a:
            continue

        for j in range(i + 1, len(course_list)):
            course_b = course_list[j]
            students_b = students_by_course.get(course_b.id, set())
            if not students_b:
                continue

            intersection = students_a.intersection(students_b)
            if intersection:
                student_conflict_graph[course_a.id].add(course_b.id)
                student_conflict_graph[course_b.id].add(course_a.id)

                union_len = len(students_a.union(students_b))
                jaccard = round(len(intersection) / union_len, 4) if union_len > 0 else 0.0
                cohort_overlaps[(course_a.id, course_b.id)] = jaccard
                cohort_overlaps[(course_b.id, course_a.id)] = jaccard

    return students_by_course, student_conflict_graph, cohort_overlaps

