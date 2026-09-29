import csv
import datetime
import io
from typing import Any, Dict, List

from courses.models import Course
from hierarchy.models import Department, Faculty, Program
from ..models.problem import SchedulingProblem


def _resolve_occurrence_branch(
    occ,
    courses_map: Dict[int | str, Course],
    departments_map: Dict[int, Department],
) -> Dict[str, Any]:
    """
    Resolves the single owning branch (Faculty, Department, Program) for an occurrence.
    If a course is targeted to a specific program, it maps to that program.
    If it is departmental/shared, it maps to the department's core program branch.
    """
    c = courses_map.get(occ.course_id)
    if c and c.target_program:
        prog = c.target_program
        dept = prog.department
        fac = dept.faculty
        return {
            "fac_id": fac.id,
            "fac_name": fac.name,
            "fac_code": fac.code,
            "dept_id": dept.id,
            "dept_name": dept.name,
            "dept_code": dept.code,
            "prog_id": prog.id,
            "prog_name": prog.name,
            "prog_code": prog.code,
            "is_shared": False,
        }
    elif c and c.owning_department:
        dept = c.owning_department
        fac = dept.faculty
        default_prog = dept.programs.filter(is_default=True).first()
        prog_id = default_prog.id if default_prog else 0
        prog_name = f"{default_prog.name} (Core)" if default_prog else f"{dept.name} (Core)"
        prog_code = default_prog.code if default_prog else dept.code
        return {
            "fac_id": fac.id,
            "fac_name": fac.name,
            "fac_code": fac.code,
            "dept_id": dept.id,
            "dept_name": dept.name,
            "dept_code": dept.code,
            "prog_id": prog_id,
            "prog_name": prog_name,
            "prog_code": prog_code,
            "is_shared": True,
        }
    elif c and c.owning_faculty:
        fac = c.owning_faculty
        return {
            "fac_id": fac.id,
            "fac_name": fac.name,
            "fac_code": fac.code,
            "dept_id": 0,
            "dept_name": "Faculty-Wide Courses",
            "dept_code": fac.code,
            "prog_id": 0,
            "prog_name": "Faculty Core",
            "prog_code": "FAC",
            "is_shared": True,
        }
    elif occ.department_id and occ.department_id in departments_map:
        dept = departments_map[occ.department_id]
        fac = dept.faculty
        default_prog = dept.programs.filter(is_default=True).first()
        prog_id = default_prog.id if default_prog else 0
        prog_name = f"{default_prog.name} (Core)" if default_prog else f"{dept.name} (Core)"
        prog_code = default_prog.code if default_prog else dept.code
        return {
            "fac_id": fac.id if fac else 0,
            "fac_name": fac.name if fac else "General / Inter-Faculty",
            "fac_code": fac.code if fac else "GEN",
            "dept_id": dept.id,
            "dept_name": dept.name,
            "dept_code": dept.code,
            "prog_id": prog_id,
            "prog_name": prog_name,
            "prog_code": prog_code,
            "is_shared": True,
        }
    else:
        return {
            "fac_id": 0,
            "fac_name": "General Studies / University",
            "fac_code": "GEN",
            "dept_id": 0,
            "dept_name": "General Studies",
            "dept_code": "GST",
            "prog_id": 0,
            "prog_name": "University Core",
            "prog_code": "GEN",
            "is_shared": True,
        }


def serialize_problem_to_dict(problem: SchedulingProblem) -> Dict[str, Any]:
    """
    Serializes a pure-data SchedulingProblem into a comprehensive hierarchical JSON structure.
    Every occurrence is represented EXACTLY ONCE under its primary owning branch
    (Faculty -> Department -> Program -> Level), with all shared cohorts explicitly listed.
    """
    courses_map: Dict[int | str, Course] = {
        c.id: c
        for c in Course.objects.filter(
            id__in=[occ.course_id for occ in problem.occurrences]
        ).select_related("target_program__department__faculty", "owning_department__faculty", "owning_faculty")
    }
    departments_map: Dict[int, Department] = {
        d.id: d for d in Department.objects.select_related("faculty").all()
    }

    faculties_dict: Dict[int, Dict[str, Any]] = {}
    all_occurrences_flat: List[Dict[str, Any]] = []

    for occ in problem.occurrences:
        lecturers_list = [
            {
                "id": l_id,
                "name": problem.lecturer_details[l_id].name,
                "staff_id": problem.lecturer_details[l_id].staff_id,
            }
            for l_id in occ.lecturer_ids
            if l_id in problem.lecturer_details
        ]
        venues_list = [
            {
                "id": v_id,
                "name": problem.venues[v_id].name,
                "capacity": problem.venues[v_id].capacity,
                "venue_type": problem.venues[v_id].venue_type,
            }
            for v_id in occ.allowed_venue_ids
            if v_id in problem.venues
        ]
        shared_cohorts = [
            f"{g.program_code or g.program_name} {g.level}L"
            for g in occ.student_groups
        ]

        branch = _resolve_occurrence_branch(occ, courses_map, departments_map)

        occ_payload = {
            "occurrence_id": occ.occurrence_id,
            "course_id": occ.course_id,
            "course_code": occ.course_code,
            "course_title": occ.course_title,
            "occurrence_index": occ.occurrence_index,
            "total_occurrences": occ.total_occurrences,
            "course_type": occ.course_type,
            "expected_students": occ.expected_students,
            "level": occ.level,
            "faculty_name": branch["fac_name"],
            "department_name": branch["dept_name"],
            "program_name": branch["prog_name"],
            "program_code": branch["prog_code"],
            "is_shared": branch["is_shared"],
            "lecturers": lecturers_list,
            "allowed_venues": venues_list,
            "shared_cohorts": shared_cohorts,
        }
        all_occurrences_flat.append(occ_payload)

        # Place occurrence ONCE into its primary owning branch
        fac_id = branch["fac_id"]
        if fac_id not in faculties_dict:
            faculties_dict[fac_id] = {
                "id": fac_id,
                "name": branch["fac_name"],
                "code": branch["fac_code"],
                "departments": {},
            }
        fac_entry = faculties_dict[fac_id]

        dept_id = branch["dept_id"]
        if dept_id not in fac_entry["departments"]:
            fac_entry["departments"][dept_id] = {
                "id": dept_id,
                "name": branch["dept_name"],
                "code": branch["dept_code"],
                "programs": {},
            }
        dept_entry = fac_entry["departments"][dept_id]

        prog_id = branch["prog_id"]
        if prog_id not in dept_entry["programs"]:
            dept_entry["programs"][prog_id] = {
                "id": prog_id,
                "name": branch["prog_name"],
                "code": branch["prog_code"],
                "levels": {},
            }
        prog_entry = dept_entry["programs"][prog_id]

        level_str = str(occ.level)
        if level_str not in prog_entry["levels"]:
            prog_entry["levels"][level_str] = {
                "level": occ.level,
                "cohort_label": f"{branch['prog_code']} {level_str}L",
                "occurrences": [],
            }
        prog_entry["levels"][level_str]["occurrences"].append(occ_payload)

    # Convert dictionary maps into clean nested lists for intuitive traversal
    hierarchy_tree = []
    for _, f in sorted(faculties_dict.items(), key=lambda x: x[1]["name"]):
        depts_list = []
        for _, d in sorted(f["departments"].items(), key=lambda x: x[1]["name"]):
            progs_list = []
            for _, p in sorted(d["programs"].items(), key=lambda x: x[1]["name"]):
                levels_list = [
                    lvl
                    for _, lvl in sorted(p["levels"].items(), key=lambda x: int(x[0]))
                ]
                progs_list.append({
                    "id": p["id"],
                    "name": p["name"],
                    "code": p["code"],
                    "levels": levels_list,
                })
            depts_list.append({
                "id": d["id"],
                "name": d["name"],
                "code": d["code"],
                "programs": progs_list,
            })
        hierarchy_tree.append({
            "id": f["id"],
            "name": f["name"],
            "code": f["code"],
            "departments": depts_list,
        })

    # Venues payload
    venues_payload = [
        {
            "id": v.id,
            "name": v.name,
            "capacity": v.capacity,
            "venue_type": v.venue_type,
            "owning_level": v.owning_level,
            "owning_scope_id": v.owning_scope_id,
        }
        for v in problem.venues.values()
    ]

    # Valid slots payload
    slots_payload = [
        {
            "slot_id": s.slot_id,
            "day": s.day,
            "day_name": s.day_name,
            "period_index": s.period_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "display": f"{s.day_name} {s.start_time}-{s.end_time}",
        }
        for s in problem.valid_slots
    ]

    # Student conflict graph
    conflict_graph_payload = {
        str(k): list(v) for k, v in problem.student_conflict_graph.items()
    }

    return {
        "metadata": {
            "semester_id": problem.semester_id,
            "scope_type": problem.scope_type,
            "scope_id": problem.scope_id,
            "scope_name": problem.scope_name,
            "total_occurrences": problem.total_occurrences,
            "total_venues": len(problem.venues),
            "total_valid_slots": len(problem.valid_slots),
            "daily_lecture_limit": problem.daily_lecture_limit,
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "hierarchy": hierarchy_tree,
        "all_occurrences": all_occurrences_flat,
        "venues": venues_payload,
        "valid_slots": slots_payload,
        "student_conflict_graph": conflict_graph_payload,
    }


def serialize_problem_to_csv(problem: SchedulingProblem) -> str:
    """
    Serializes the scheduling problem occurrences into CSV format.
    Every occurrence is output EXACTLY ONCE with its full owning hierarchy and shared cohorts.
    """
    courses_map: Dict[int | str, Course] = {
        c.id: c
        for c in Course.objects.filter(
            id__in=[occ.course_id for occ in problem.occurrences]
        ).select_related("target_program__department__faculty", "owning_department__faculty", "owning_faculty")
    }
    departments_map: Dict[int, Department] = {
        d.id: d for d in Department.objects.select_related("faculty").all()
    }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Occurrence ID",
        "Course Code",
        "Course Title",
        "Occurrence Index",
        "Total Occurrences",
        "Level",
        "Course Type",
        "Faculty Code",
        "Faculty Name",
        "Department Code",
        "Department Name",
        "Program Code",
        "Program Scope",
        "Expected Students",
        "Lecturers",
        "Allowed Venues",
        "Shared Cohorts",
    ])

    rows = []

    for occ in problem.occurrences:
        branch = _resolve_occurrence_branch(occ, courses_map, departments_map)

        lecturers_list = [
            f"{problem.lecturer_details[l_id].name} ({problem.lecturer_details[l_id].staff_id})"
            for l_id in occ.lecturer_ids
            if l_id in problem.lecturer_details
        ]
        venues_list = [
            f"{problem.venues[v_id].name} [cap: {problem.venues[v_id].capacity}]"
            for v_id in occ.allowed_venue_ids
            if v_id in problem.venues
        ]
        shared_cohorts_str = ", ".join(
            f"{g.program_code or g.program_name} {g.level}L"
            for g in occ.student_groups
        )
        lecturers_str = "; ".join(lecturers_list)
        venues_str = "; ".join(venues_list)

        rows.append((
            occ.occurrence_id,
            occ.course_code,
            occ.course_title,
            occ.occurrence_index,
            occ.total_occurrences,
            occ.level,
            occ.course_type,
            branch["fac_code"],
            branch["fac_name"],
            branch["dept_code"],
            branch["dept_name"],
            branch["prog_code"],
            branch["prog_name"],
            occ.expected_students,
            lecturers_str,
            venues_str,
            shared_cohorts_str,
        ))

    # Sort rows by Faculty, Department, Level, Course Code, Occurrence Index
    rows.sort(key=lambda r: (r[8], r[10], r[5], r[1], r[3]))

    for r in rows:
        writer.writerow(r)

    return output.getvalue()
