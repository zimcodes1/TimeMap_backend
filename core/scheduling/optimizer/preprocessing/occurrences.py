from typing import List

from ..models.course import CourseData
from ..models.occurrence import CourseOccurrence


def expand_occurrences(courses: List[CourseData]) -> List[CourseOccurrence]:
    """
    Expands courses into individual CourseOccurrence units based on
    required_occurrences.
    Each occurrence becomes a distinct gene in the GA chromosome.
    """
    occurrences: List[CourseOccurrence] = []

    for course in courses:
        total = max(1, course.required_occurrences)
        for idx in range(1, total + 1):
            occ_id = f"{course.code}-{idx}"
            occurrences.append(
                CourseOccurrence(
                    occurrence_id=occ_id,
                    course_id=course.id,
                    course_code=course.code,
                    course_title=course.title,
                    occurrence_index=idx,
                    total_occurrences=total,
                    student_groups=course.student_groups,
                    lecturer_ids=course.lecturer_ids,
                    allowed_venue_ids=course.allowed_venue_ids,
                    course_type=course.course_type,
                    expected_students=course.expected_students,
                    department_id=course.department_id,
                    department_name=course.department_name,
                    level=course.level,
                )
            )

    return occurrences

