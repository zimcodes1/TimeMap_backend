from collections import defaultdict
from typing import Dict, List, Set, Tuple

from ..models.course import CourseData
from ..models.student_group import StudentGroup


def build_student_conflict_graph(
    courses: List[CourseData],
) -> Tuple[
    Dict[int | str, Set[int | str]],
    Dict[Tuple[int | str, int | str], List[StudentGroup]],
]:
    """
    Precomputes student conflict relationships between courses.
    Two courses conflict if their assigned StudentGroup sets intersect.
    Returns:
      - conflict_graph: maps course_id -> set of conflicting course_ids
      - shared_groups: maps (course_a_id, course_b_id) -> list of shared StudentGroups
    """
    conflict_graph: Dict[int | str, Set[int | str]] = defaultdict(set)
    shared_groups: Dict[Tuple[int | str, int | str], List[StudentGroup]] = {}

    course_groups = {c.id: set(c.student_groups) for c in courses}
    course_ids = list(course_groups.keys())

    for i in range(len(course_ids)):
        cid_a = course_ids[i]
        groups_a = course_groups[cid_a]
        for j in range(i + 1, len(course_ids)):
            cid_b = course_ids[j]
            groups_b = course_groups[cid_b]

            intersection = list(groups_a & groups_b)
            if intersection:
                conflict_graph[cid_a].add(cid_b)
                conflict_graph[cid_b].add(cid_a)
                shared_groups[(cid_a, cid_b)] = intersection
                shared_groups[(cid_b, cid_a)] = intersection

    return dict(conflict_graph), shared_groups

