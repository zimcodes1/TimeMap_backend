from typing import Any, Dict
from django.db import transaction

from ..models import LectureSession, TimetableEntry, TimetableGenerationRun
from ..services import materialize_timetable_entry

DAY_CODE_TO_NAME = {
    "MO": "monday",
    "TU": "tuesday",
    "WE": "wednesday",
    "TH": "thursday",
    "FR": "friday",
}


@transaction.atomic
def publish_generation_run(
    generation_run: TimetableGenerationRun,
    created_by_admin=None,
) -> Dict[str, Any]:
    """
    Applies the generated timetable assignments from a TimetableGenerationRun into
    active TimetableEntry rows and materializes all LectureSessions across the semester.
    Replaces existing lecture timetable entries in the target scope for this semester.
    """
    if not generation_run.assignments_payload:
        raise ValueError("Cannot publish an empty or failed generation run.")

    semester = generation_run.semester
    start_date = semester.lecture_start_date or semester.start_date
    end_date = semester.lecture_end_date or semester.end_date

    scope_type = generation_run.scope_type
    scope_id = generation_run.scope_id

    # 1. Clean up previously generated lecture entries for this scope & semester
    existing_entries_qs = TimetableEntry.objects.filter(
        semester=semester,
        entry_type=TimetableEntry.EntryType.LECTURE,
    )

    if scope_type == "school":
        existing_entries_qs = existing_entries_qs.filter(
            course__owning_school_id=scope_id
        ) | existing_entries_qs.filter(
            course__owning_faculty__school_id=scope_id
        ) | existing_entries_qs.filter(
            course__owning_department__faculty__school_id=scope_id
        )
    elif scope_type == "faculty":
        existing_entries_qs = existing_entries_qs.filter(
            course__owning_faculty_id=scope_id
        ) | existing_entries_qs.filter(
            course__owning_department__faculty_id=scope_id
        )
    elif scope_type == "department":
        existing_entries_qs = existing_entries_qs.filter(
            course__owning_department_id=scope_id
        )

    # Delete existing sessions & entries
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

    # 3. Mark generation run as published
    generation_run.is_published = True
    generation_run.save(update_fields=["is_published"])

    return {
        "generation_run_id": str(generation_run.id),
        "status": "published",
        "published_entries_count": created_entries_count,
        "materialized_sessions_count": total_sessions_count,
    }

