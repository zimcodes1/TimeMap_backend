from typing import Dict, List, Set

from ..models.course import CourseData
from ..models.venue import VenueData


def filter_allowed_venues(
    course: CourseData,
    all_venues: List[VenueData],
) -> List[int | str]:
    """
    Resolves the allowed venues for a given course prior to GA initialization
    according to the hierarchical venue access model:

      - Practical courses MUST use laboratories (venue.is_laboratory is True).
      - Ordinary lecture courses MUST use lecture halls or multipurpose halls (venue.is_laboratory is False).
      - If course.allowed_venue_ids is explicitly provided, only venues in that list matching
        the type constraint and access rules are included.

      Hierarchical Access Rules:
        1. General courses (course.is_general or course.owning_level == "general"):
           Allowed all venues within scope matching the type constraint.
        2. Department courses (course.owning_level == "department" or course.department_id):
           Allowed:
             - Originating department's venues (venue.owning_department_id == course.department_id)
             - Receiving department(s)' venues if shared (venue.owning_department_id in course.receiving_department_ids)
             - Faculty venues that do NOT belong to any department:
               (venue.owning_level == "faculty" and venue.owning_department_id is None)
             - School venues that do NOT belong to any department:
               (venue.owning_level == "school" and venue.owning_department_id is None)
           Strict rule: strictly avoids allowing venues owned by other departments.
        3. Faculty courses (course.owning_level == "faculty" without department):
           Allowed ONLY faculty & school venues that belong to no departments (plus receiving departments if shared).
        4. School courses (course.owning_level == "school"):
           Allowed school & faculty venues that belong to no departments.
    """
    is_practical = course.is_practical
    explicit_ids = set(course.allowed_venue_ids) if course.allowed_venue_ids else None

    owning_dept_id = str(course.department_id) if course.department_id else None
    recv_dept_ids = {str(d) for d in course.receiving_department_ids if d}
    allowed_dept_ids: Set[str] = set()
    if owning_dept_id:
        allowed_dept_ids.add(owning_dept_id)
    allowed_dept_ids.update(recv_dept_ids)

    course_fac_id = str(course.faculty_id) if course.faculty_id else None

    allowed: List[int | str] = []
    for venue in all_venues:
        # 1. Explicit IDs restriction if provided
        if explicit_ids is not None and venue.id not in explicit_ids:
            continue

        # 2. Type constraint: practical courses must use laboratory; lecture courses must not
        if is_practical:
            if not venue.is_laboratory:
                continue
        else:
            if venue.is_laboratory:
                continue

        # 3. Ownership / Hierarchy constraint
        v_dept_id = str(venue.owning_department_id) if venue.owning_department_id is not None else None
        v_fac_id = str(venue.owning_faculty_id) if venue.owning_faculty_id is not None else None
        v_level = venue.owning_level.lower() if venue.owning_level else "school"

        # Case 1: General course within scope
        if course.is_general or course.owning_level == "general":
            allowed.append(venue.id)
            continue

        # Case 2: Department-level course
        if course.owning_level == "department" or owning_dept_id:
            if v_dept_id is not None:
                # Strictly allowed ONLY if it matches owning department or receiving departments
                if v_dept_id in allowed_dept_ids:
                    allowed.append(venue.id)
            else:
                # Faculty or school venue belonging to NO department
                if v_level == "faculty":
                    if course_fac_id is None or v_fac_id is None or v_fac_id == course_fac_id:
                        allowed.append(venue.id)
                elif v_level == "school":
                    allowed.append(venue.id)
            continue

        # Case 3: Faculty-level course
        if course.owning_level == "faculty":
            if v_dept_id is not None:
                # Allowed only if shared with this department
                if v_dept_id in recv_dept_ids:
                    allowed.append(venue.id)
            else:
                # Faculty & school venues belonging to no departments
                if v_level == "faculty":
                    if course_fac_id is None or v_fac_id is None or v_fac_id == course_fac_id:
                        allowed.append(venue.id)
                elif v_level == "school":
                    allowed.append(venue.id)
            continue

        # Case 4: School-level course
        if course.owning_level == "school":
            if v_dept_id is not None:
                if v_dept_id in recv_dept_ids:
                    allowed.append(venue.id)
            else:
                allowed.append(venue.id)
            continue

        # Fallback for unrecognized level: only if no department or matching department
        if v_dept_id is None or (owning_dept_id and v_dept_id in allowed_dept_ids):
            allowed.append(venue.id)

    # Safety fallback: If practical course has no lab in its immediate hierarchy,
    # fallback to available labs in the faculty/school rather than 0 allowed venues.
    if is_practical and not allowed:
        faculty_or_school_labs = [
            v.id
            for v in all_venues
            if v.is_laboratory
            and (
                v_fac_id == course_fac_id
                or (v.owning_level and v.owning_level.lower() in ("faculty", "school"))
            )
        ]
        if not faculty_or_school_labs:
            faculty_or_school_labs = [v.id for v in all_venues if v.is_laboratory]
        allowed.extend(faculty_or_school_labs)
    elif not is_practical and not allowed:
        fallback_halls = [
            v.id
            for v in all_venues
            if not v.is_laboratory
            and (
                v_fac_id == course_fac_id
                or (v.owning_level and v.owning_level.lower() in ("faculty", "school"))
            )
        ]
        if not fallback_halls:
            fallback_halls = [v.id for v in all_venues if not v.is_laboratory]
        allowed.extend(fallback_halls)

    return allowed


def build_allowed_venues_map(
    courses: List[CourseData],
    all_venues: List[VenueData],
) -> Dict[int | str, List[int | str]]:
    """
    Builds a map of course_id -> list of allowed venue_ids for all courses.
    """
    return {c.id: filter_allowed_venues(c, all_venues) for c in courses}
