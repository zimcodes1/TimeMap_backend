from typing import Any, Dict
from django.db import models, transaction

from ..models import LectureSession, TimetableEntry, TimetableGenerationRun
from ..services import materialize_timetable_entry

DAY_CODE_TO_NAME = {
    "MO": "monday",
    "TU": "tuesday",
    "WE": "wednesday",
    "TH": "thursday",
    "FR": "friday",
}


def _originating_course_filter(scope_type: str, scope_id: int) -> models.Q:
    """
    Returns a Q filter that matches TimetableEntry rows whose course ORIGINATES
    from the given scope — i.e., courses owned by this department/faculty/school,
    excluding courses merely shared/granted into it via CourseAccessGrant.

    This is used during publish to avoid overwriting entries produced by a
    higher-scope run for shared or faculty/school-level courses.
    """
    if scope_type == "school":
        return (
            models.Q(course__owning_school_id=scope_id)
            | models.Q(course__owning_faculty__school_id=scope_id)
            | models.Q(course__owning_department__faculty__school_id=scope_id)
        )
    elif scope_type == "faculty":
        # Only courses whose owning_faculty is this faculty or owning_department is under this faculty.
        # Excludes school-level or general courses that were merely included in the faculty run.
        return (
            models.Q(course__owning_faculty_id=scope_id)
            | models.Q(course__owning_department__faculty_id=scope_id)
        )
    elif scope_type == "department":
        # Only courses directly owned by this department.
        # Excludes courses shared to this department via CourseAccessGrant.
        return models.Q(course__owning_department_id=scope_id)
    else:
        return models.Q(pk__in=[])


@transaction.atomic
def publish_generation_run(
    generation_run: TimetableGenerationRun,
    created_by_admin=None,
) -> Dict[str, Any]:
    """
    Applies the generated timetable assignments from a TimetableGenerationRun into
    active TimetableEntry rows and materializes all LectureSessions across the semester.

    Scope guard: only deletes and recreates TimetableEntry records for courses that
    ORIGINATE from the generating scope (owned by that department/faculty/school).
    Shared/granted courses and entries created by higher-scope published runs are
    left untouched.  This prevents a department publish from overwriting faculty-level
    or school-level entries, and vice versa.
    """
    if not generation_run.assignments_payload:
        raise ValueError("Cannot publish an empty or failed generation run.")

    semester = generation_run.semester
    start_date = semester.lecture_start_date or semester.start_date
    end_date = semester.lecture_end_date or semester.end_date

    scope_type = generation_run.scope_type
    scope_id = generation_run.scope_id

    # 1. Clean up previously generated lecture entries for this scope & semester,
    #    but ONLY for courses that originate from this scope (not shared/granted ones).
    originating_filter = _originating_course_filter(scope_type, scope_id)
    existing_entries_qs = TimetableEntry.objects.filter(
        semester=semester,
        entry_type=TimetableEntry.EntryType.LECTURE,
    ).filter(originating_filter)

    # Delete existing sessions & entries for originating courses only
    LectureSession.objects.filter(timetable_entry__in=existing_entries_qs).delete()
    existing_entries_qs.delete()

    created_entries_count = 0
    total_sessions_count = 0

    # 2. Iterate assignments and create TimetableEntry instances
    for item in generation_run.assignments_payload:
        day_code = item["day"]
        day_name = DAY_CODE_TO_NAME.get(day_code, "monday")
        recurrence_rule = f"weekly:{day_name}"

        # Resolve admin profile if available
        admin_prof = None
        if created_by_admin:
            admin_prof = getattr(created_by_admin, "admin_profile", None)
        if not admin_prof and generation_run.initiated_by:
            admin_prof = getattr(generation_run.initiated_by, "admin_profile", None)

        entry = TimetableEntry.objects.create(
            entry_type=TimetableEntry.EntryType.LECTURE,
            title=f"{item['course_code']} Lecture ({item.get('occurrence_index', 1)})",
            course_id=item["course_id"],
            venue_id=item["venue_id"],
            start_time=item["start_time"],
            end_time=item["end_time"],
            recurrence_rule=recurrence_rule,
            recurrence_start_date=start_date,
            recurrence_end_date=end_date,
            semester=semester,
            status=TimetableEntry.Status.SCHEDULED,
            created_by=admin_prof,
        )

        # Materialize weekly lecture sessions across semester
        sessions = materialize_timetable_entry(entry)
        created_entries_count += 1
        total_sessions_count += len(sessions)

    # 3. Unpublish previous runs in this scope and semester so only one live run exists.
    #    For a department run, only unpublish other department runs for the same dept.
    #    For a faculty run, unpublish faculty runs for the same faculty (NOT school-level runs).
    #    For a school run, unpublish all runs under the school.
    previous_published = TimetableGenerationRun.objects.filter(
        semester=semester,
        is_published=True,
    ).exclude(id=generation_run.id)

    if scope_type == "school":
        previous_published.update(is_published=False)
    elif scope_type == "faculty":
        from hierarchy.models import Department
        dept_ids = list(Department.objects.filter(faculty_id=scope_id).values_list("id", flat=True))
        previous_published.filter(
            models.Q(scope_type="faculty", scope_id=scope_id)
            | models.Q(scope_type="department", scope_id__in=dept_ids)
        ).update(is_published=False)
    elif scope_type == "department":
        previous_published.filter(
            scope_type="department",
            scope_id=scope_id,
        ).update(is_published=False)

    generation_run.is_published = True
    generation_run.save(update_fields=["is_published"])

    return {
        "generation_run_id": str(generation_run.id),
        "status": "published",
        "published_entries_count": created_entries_count,
        "materialized_sessions_count": total_sessions_count,
    }
