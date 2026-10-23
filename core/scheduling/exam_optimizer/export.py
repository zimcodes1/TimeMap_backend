"""Serialization and export utilities for the pure-data ExamSchedulingProblem."""

import csv
import datetime
import io
from typing import Any, Dict, List, Set

from courses.models import Course
from hierarchy.models import Department, Faculty
from venues.models import Venue

from .models.problem import ExamSchedulingProblem


def _resolve_event_branch(
    event,
    courses_map: Dict[int | str, Course],
) -> Dict[str, Any]:
    """Resolves the owning academic hierarchy branch (Faculty, Department, Program) for an exam event."""
    c = courses_map.get(event.course_id)
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
    elif c and c.owning_school:
        sch = c.owning_school
        return {
            "fac_id": 0,
            "fac_name": "School-Wide General Courses",
            "fac_code": getattr(sch, "code", "") or "SCH",
            "dept_id": 0,
            "dept_name": "General Studies",
            "dept_code": "GST",
            "prog_id": 0,
            "prog_name": "School Core",
            "prog_code": "GEN",
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


def serialize_exam_problem_to_dict(problem: ExamSchedulingProblem) -> Dict[str, Any]:
    """Serializes a pure-data ExamSchedulingProblem into a comprehensive hierarchical JSON structure.

    Matches the exact schema, depth, and conventions established by the timetable problem export.
    """
    courses_map: Dict[int | str, Course] = {
        c.id: c
        for c in Course.objects.filter(
            id__in=[e.course_id for e in problem.events.values()]
        ).select_related(
            "target_program__department__faculty",
            "owning_department__faculty",
            "owning_faculty",
            "owning_school",
        )
    }

    faculties_dict: Dict[int, Dict[str, Any]] = {}
    all_events_flat: List[Dict[str, Any]] = []

    # Map all unique venues across types
    unique_venues_map: Dict[int, Any] = {}
    venue_compatible_types: Dict[int, Set[str]] = {}
    for exam_type, v_list in problem.venues_by_type.items():
        for v in v_list:
            unique_venues_map[v.id] = v
            venue_compatible_types.setdefault(v.id, set()).add(exam_type)

    for event in problem.ordered_events:
        branch = _resolve_event_branch(event, courses_map)

        compatible_venues_list = [
            {
                "id": v.id,
                "name": v.name,
                "code": getattr(v, "code", "") or "",
                "capacity": int(getattr(v, "exam_capacity", None) or getattr(v, "capacity", 0)),
                "venue_type": getattr(v, "venue_type", ""),
            }
            for v in problem.venues_by_type.get(event.exam_type, [])
        ]

        conflicts_list = sorted(list(problem.student_conflict_graph.get(event.course_id, set())))

        populations_payload = [
            {
                "course_id": p.course_id,
                "department_id": p.department_id,
                "department_name": p.department_name,
                "program_id": p.program_id,
                "program_name": p.program_name,
                "level": p.level,
                "student_count": p.student_count,
            }
            for p in event.populations
        ]

        shared_cohorts = [
            f"{p.program_name or p.department_name or 'Cohort'} {p.level}L"
            for p in event.populations
        ]

        event_payload = {
            "event_id": f"EXAM-{event.course_code}",
            "course_id": event.course_id,
            "course_code": event.course_code,
            "course_title": event.course_title,
            "course_level": event.course_level,
            "exam_type": event.exam_type,
            "duration_minutes": event.duration_minutes,
            "duration_per_student_minutes": event.duration_per_student_minutes,
            "expected_students": event.student_count,
            "conflict_degree": event.conflict_degree,
            "venue_scarcity": round(event.venue_scarcity, 4),
            "faculty_name": branch["fac_name"],
            "department_name": branch["dept_name"],
            "program_name": branch["prog_name"],
            "program_code": branch["prog_code"],
            "is_shared": branch["is_shared"],
            "populations": populations_payload,
            "shared_cohorts": shared_cohorts,
            "allowed_venues": compatible_venues_list,
            "conflicting_course_ids": conflicts_list,
        }
        all_events_flat.append(event_payload)

        # Place event ONCE into its primary owning branch
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

        level_str = str(event.course_level)
        if level_str not in prog_entry["levels"]:
            prog_entry["levels"][level_str] = {
                "level": event.course_level,
                "cohort_label": f"{branch['prog_code']} {level_str}L",
                "events": [],
            }
        prog_entry["levels"][level_str]["events"].append(event_payload)

    # Convert dictionary maps into clean nested lists
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
            "code": getattr(v, "code", "") or "",
            "venue_type": getattr(v, "venue_type", ""),
            "capacity": getattr(v, "capacity", 0),
            "exam_capacity": getattr(v, "exam_capacity", None),
            "effective_exam_capacity": int(getattr(v, "exam_capacity", None) or getattr(v, "capacity", 0)),
            "location": getattr(v, "location", "") or "",
            "owning_level": getattr(v, "owning_level", ""),
            "compatible_exam_types": sorted(list(venue_compatible_types.get(v.id, set()))),
            "facilities": [f.name for f in v.facilities.all()] if hasattr(v, "facilities") else [],
        }
        for v in sorted(unique_venues_map.values(), key=lambda x: x.name)
    ]

    # Candidate windows payload
    candidate_windows_payload = [
        {
            "window_id": f"{w.date.isoformat()}_{w.start_time.strftime('%H:%M')}-{w.end_time.strftime('%H:%M')}_{w.duration_minutes}m",
            "date": w.date.isoformat(),
            "day_name": w.date.strftime("%A"),
            "start_time": w.start_time.strftime("%H:%M"),
            "end_time": w.end_time.strftime("%H:%M"),
            "duration_minutes": w.duration_minutes,
            "display": f"{w.date.strftime('%a, %b %d, %Y')} {w.start_time.strftime('%H:%M')}-{w.end_time.strftime('%H:%M')} ({w.duration_minutes}m)",
        }
        for w in problem.candidate_windows
    ]

    # Student conflict graph
    conflict_graph_payload = {
        str(k): sorted(list(v)) for k, v in problem.student_conflict_graph.items()
    }

    # Cohort overlaps payload
    cohort_overlaps_payload = [
        {"course_1": c1, "course_2": c2, "jaccard_similarity": round(sim, 4)}
        for (c1, c2), sim in problem.cohort_overlaps.items()
    ]

    # Event and student counts broken down by examination type
    events_by_exam_type = {"written": 0, "cbt": 0, "lab_practical": 0}
    students_by_exam_type = {"written": 0, "cbt": 0, "lab_practical": 0}
    for event in problem.events.values():
        t = event.exam_type or "written"
        events_by_exam_type[t] = events_by_exam_type.get(t, 0) + 1
        students_by_exam_type[t] = students_by_exam_type.get(t, 0) + event.student_count

    return {
        "metadata": {
            "semester_id": problem.semester_id,
            "semester_label": problem.semester_label,
            "scope_type": problem.scope_type,
            "scope_id": problem.scope_id,
            "scope_name": problem.scope_name,
            "start_date": problem.start_date.isoformat(),
            "end_date": problem.end_date.isoformat(),
            "total_events": problem.total_events,
            "events_by_exam_type": events_by_exam_type,
            "total_students": problem.total_students,
            "students_by_exam_type": students_by_exam_type,
            "total_venues": len(unique_venues_map),
            "venues_by_exam_type": {k: len(v) for k, v in problem.venues_by_type.items()},
            "total_candidate_windows": len(problem.candidate_windows),
            "calendar_policy": {
                "operating_days": list(problem.policy.operating_days),
                "open_time": problem.policy.open_time.strftime("%H:%M"),
                "close_time": problem.policy.close_time.strftime("%H:%M"),
                "step_minutes": problem.policy.step_minutes,
                "jummat_day": problem.policy.jummat_day,
                "jummat_start": f"{problem.policy.jummat_start_minutes // 60}:00",
                "jummat_end": f"{problem.policy.jummat_end_minutes // 60}:00",
            },
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "hierarchy": hierarchy_tree,
        "all_events": all_events_flat,
        "venues": venues_payload,
        "candidate_windows": candidate_windows_payload,
        "student_conflict_graph": conflict_graph_payload,
        "cohort_overlaps": cohort_overlaps_payload,
    }


def serialize_exam_problem_to_csv(problem: ExamSchedulingProblem) -> str:
    """Serializes the exam scheduling problem events into CSV format.

    Every exam event is output with its owning academic hierarchy branch, student counts,
    duration, exam type, participating cohorts, and eligible venue counts.
    """
    courses_map: Dict[int | str, Course] = {
        c.id: c
        for c in Course.objects.filter(
            id__in=[e.course_id for e in problem.events.values()]
        ).select_related("target_program__department__faculty", "owning_department__faculty", "owning_faculty")
    }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Event ID",
        "Course Code",
        "Course Title",
        "Level",
        "Exam Type",
        "Duration (Minutes)",
        "Per-Student Duration (Minutes)",
        "Expected Students",
        "Faculty Code",
        "Faculty Name",
        "Department Code",
        "Department Name",
        "Program Code",
        "Program Name",
        "Participating Cohorts",
        "Eligible Venues Count",
        "Conflicting Courses Count",
    ])

    for event in problem.ordered_events:
        branch = _resolve_event_branch(event, courses_map)

        cohorts_str = "; ".join(
            f"{pop.program_name or pop.department_name or 'General'}:{pop.level} ({pop.student_count})"
            for pop in event.populations
        ) or "None"

        eligible_venues = problem.venues_by_type.get(event.exam_type, [])
        conflict_count = len(problem.student_conflict_graph.get(event.course_id, set()))

        writer.writerow([
            f"EVT_{event.course_id}",
            event.course_code,
            event.course_title,
            event.course_level,
            event.exam_type,
            event.duration_minutes,
            event.duration_per_student_minutes if event.duration_per_student_minutes is not None else "N/A",
            event.student_count,
            branch["fac_code"],
            branch["fac_name"],
            branch["dept_code"],
            branch["dept_name"],
            branch["prog_code"],
            branch["prog_name"],
            cohorts_str,
            len(eligible_venues),
            conflict_count,
        ])

    return output.getvalue()


