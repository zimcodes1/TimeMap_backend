import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student, User
from accounts.permissions import (
    get_user_scope_departments,
    get_user_scope_faculties,
    get_user_scope_schools,
)
from courses.models import Course, CourseRegistration
from django.db.models import Q
from venues.models import Venue

from .models import ExamSitting, LectureSession, TimetableEntry
from .services import parse_target_weekdays


def check_interval_overlap(start1, end1, start2, end2):
    """
    Standard interval overlap check.
    Returns True if intervals overlap, False if they are disjoint or adjacent.
    (e.g., 10:00-11:00 and 11:00-12:00 do NOT overlap).
    """
    return start1 < end2 and end1 > start2


def check_venue_overlap(
    venue,
    date,
    start_time,
    end_time,
    recurrence_rule=None,
    recurrence_start_date=None,
    recurrence_end_date=None,
    exclude_entry_id=None,
    exclude_session_id=None,
):
    """
    Checks venue double-bookings against materialized LectureSessions and one-off TimetableEntries/ExamSittings.
    If recurrence parameters are provided, checks every projected session date in the recurrence range.
    """
    conflicts = []

    # If recurring rule provided, expand dates and check each
    if recurrence_rule and recurrence_start_date and recurrence_end_date:
        target_weekdays = parse_target_weekdays(recurrence_rule)
        current = recurrence_start_date
        while current <= recurrence_end_date:
            if current.weekday() in target_weekdays:
                date_conflicts = check_venue_overlap(
                    venue=venue,
                    date=current,
                    start_time=start_time,
                    end_time=end_time,
                    exclude_entry_id=exclude_entry_id,
                    exclude_session_id=exclude_session_id,
                )
                conflicts.extend(date_conflicts)
            current += datetime.timedelta(days=1)
        return conflicts

    # Single date check against LectureSession instances
    session_qs = LectureSession.objects.filter(
        venue=venue,
        session_date=date,
        session_start_time__lt=end_time,
        session_end_time__gt=start_time,
    ).exclude(status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED])

    if exclude_session_id:
        session_qs = session_qs.exclude(id=exclude_session_id)
    if exclude_entry_id:
        session_qs = session_qs.exclude(timetable_entry_id=exclude_entry_id)

    for session in session_qs:
        conflicts.append(
            {
                "type": "venue_clash",
                "venue_id": venue.id,
                "venue_name": venue.name,
                "date": date.strftime("%Y-%m-%d") if isinstance(date, (datetime.date, datetime.datetime)) else str(date),
                "start_time": session.session_start_time.strftime("%H:%M:%S") if isinstance(session.session_start_time, datetime.time) else str(session.session_start_time),
                "end_time": session.session_end_time.strftime("%H:%M:%S") if isinstance(session.session_end_time, datetime.time) else str(session.session_end_time),
                "conflicting_title": session.timetable_entry.title,
                "conflicting_entry_id": session.timetable_entry_id,
                "conflicting_session_id": session.id,
            }
        )

    # Check non-recurring / one-off TimetableEntry entries on that date (exams, events)
    entry_qs = TimetableEntry.objects.filter(
        venue=venue,
        start_time__lt=end_time,
        end_time__gt=start_time,
    ).exclude(status__in=[TimetableEntry.Status.CANCELLED, TimetableEntry.Status.POSTPONED])

    if exclude_entry_id:
        entry_qs = entry_qs.exclude(id=exclude_entry_id)

    for entry in entry_qs:
        # Check if entry falls on date (either non-recurring, or matching recurrence_start_date for one-off exams/events)
        if not entry.recurrence_rule:
            is_match = False
            if entry.recurrence_start_date and entry.recurrence_start_date == date:
                is_match = True
            elif entry.created_at and entry.created_at.date() == date:
                is_match = True

            if is_match:
                # Avoid duplicate if already caught via materialized session
                if not any(c.get("conflicting_entry_id") == entry.id for c in conflicts):
                    conflicts.append(
                        {
                            "type": "venue_clash",
                            "venue_id": venue.id,
                            "venue_name": venue.name,
                            "date": date.strftime("%Y-%m-%d") if isinstance(date, (datetime.date, datetime.datetime)) else str(date),
                            "start_time": entry.start_time.strftime("%H:%M:%S") if isinstance(entry.start_time, datetime.time) else str(entry.start_time),
                            "end_time": entry.end_time.strftime("%H:%M:%S") if isinstance(entry.end_time, datetime.time) else str(entry.end_time),
                            "conflicting_title": entry.title,
                            "conflicting_entry_id": entry.id,
                        }
                    )

    return conflicts


def check_student_exam_clash(course, date, start_time, end_time, academic_session, exclude_entry_id=None):
    """
    Checks if any student registered for `course` has another exam sitting at an overlapping time on `date`.
    Returns list of affected students and conflicting exams.
    """
    if not course:
        return []

    # Get students registered for this course
    student_ids = CourseRegistration.objects.filter(
        course=course, academic_session=academic_session
    ).values_list("student_id", flat=True)

    if not student_ids:
        return []

    # Find existing exam sittings on the same date overlapping in time
    exam_qs = ExamSitting.objects.filter(
        timetable_entry__recurrence_start_date=date,
        timetable_entry__start_time__lt=end_time,
        timetable_entry__end_time__gt=start_time,
    ).exclude(timetable_entry__status__in=[TimetableEntry.Status.CANCELLED, TimetableEntry.Status.POSTPONED])

    if exclude_entry_id:
        exam_qs = exam_qs.exclude(timetable_entry_id=exclude_entry_id)

    clashes = []
    for exam in exam_qs:
        if exam.timetable_entry.course_id == course.id:
            continue

        # Find students registered for both courses
        other_student_ids = CourseRegistration.objects.filter(
            course=exam.timetable_entry.course, academic_session=academic_session
        ).values_list("student_id", flat=True)

        common_student_ids = set(student_ids).intersection(set(other_student_ids))
        if common_student_ids:
            affected_students = Student.objects.filter(id__in=common_student_ids)
            clashes.append(
                {
                    "type": "student_exam_clash",
                    "date": date.strftime("%Y-%m-%d") if isinstance(date, (datetime.date, datetime.datetime)) else str(date),
                    "conflicting_course_code": exam.timetable_entry.course.code if exam.timetable_entry.course else "Unknown",
                    "conflicting_exam_title": exam.timetable_entry.title,
                    "affected_student_count": len(common_student_ids),
                    "affected_students": [
                        {"id": s.id, "matric_number": s.matric_number, "full_name": s.full_name}
                        for s in affected_students
                    ],
                }
            )

    return clashes


def check_lecturer_clash(lecturer_ids, date, start_time, end_time, exclude_entry_id=None, exclude_session_id=None):
    """
    Checks if any assigned lecturer or invigilator has an overlapping teaching session or exam duty on `date`.
    """
    if not lecturer_ids:
        return []

    clashes = []
    lecturers = LecturerStaff.objects.filter(id__in=lecturer_ids)

    for lecturer in lecturers:
        # Check teaching sessions
        session_qs = LectureSession.objects.filter(
            session_date=date,
            session_start_time__lt=end_time,
            session_end_time__gt=start_time,
            timetable_entry__course__lecturers=lecturer,
        ).exclude(status__in=[LectureSession.Status.CANCELLED, LectureSession.Status.POSTPONED])

        if exclude_session_id:
            session_qs = session_qs.exclude(id=exclude_session_id)
        if exclude_entry_id:
            session_qs = session_qs.exclude(timetable_entry_id=exclude_entry_id)

        for session in session_qs:
            clashes.append(
                {
                    "type": "lecturer_clash",
                    "lecturer_id": lecturer.id,
                    "lecturer_name": lecturer.full_name,
                    "date": date.strftime("%Y-%m-%d") if isinstance(date, (datetime.date, datetime.datetime)) else str(date),
                    "conflicting_activity": f"Teaching {session.timetable_entry.title}",
                    "conflicting_entry_id": session.timetable_entry_id,
                }
            )

        # Check invigilation duties
        exam_qs = ExamSitting.objects.filter(
            timetable_entry__recurrence_start_date=date,
            timetable_entry__start_time__lt=end_time,
            timetable_entry__end_time__gt=start_time,
            invigilators=lecturer,
        ).exclude(timetable_entry__status__in=[TimetableEntry.Status.CANCELLED, TimetableEntry.Status.POSTPONED])

        if exclude_entry_id:
            exam_qs = exam_qs.exclude(timetable_entry_id=exclude_entry_id)

        for exam in exam_qs:
            clashes.append(
                {
                    "type": "lecturer_clash",
                    "lecturer_id": lecturer.id,
                    "lecturer_name": lecturer.full_name,
                    "date": date.strftime("%Y-%m-%d") if isinstance(date, (datetime.date, datetime.datetime)) else str(date),
                    "conflicting_activity": f"Invigilating {exam.timetable_entry.title}",
                    "conflicting_entry_id": exam.timetable_entry_id,
                }
            )

    return clashes


def is_venue_within_user_scope(user, venue):
    """
    Determines whether a venue falls within the user's scope (or downward hierarchy).
    - Department Admin: only venues owned by their specific department.
    - Faculty Admin: venues owned by their faculty, or departments under their faculty.
    - School Admin: venues owned by their school, or faculties/departments under their school.
    """
    if not user or not user.is_authenticated:
        return False

    if user.role == "admin" and hasattr(user, "admin_profile"):
        admin_prof = user.admin_profile

        if admin_prof.level == "department" and admin_prof.scope_department:
            return (
                venue.owning_level == Venue.OwningLevel.DEPARTMENT
                and venue.owning_department_id == admin_prof.scope_department.id
            )
        elif admin_prof.level == "faculty" and admin_prof.scope_faculty:
            if venue.owning_level == Venue.OwningLevel.FACULTY:
                return venue.owning_faculty_id == admin_prof.scope_faculty.id
            elif venue.owning_level == Venue.OwningLevel.DEPARTMENT and venue.owning_department:
                return venue.owning_department.faculty_id == admin_prof.scope_faculty.id
            return False
        elif admin_prof.level == "school" and admin_prof.scope_school:
            if venue.owning_level == Venue.OwningLevel.SCHOOL:
                return venue.owning_school_id == admin_prof.scope_school.id
            elif venue.owning_level == Venue.OwningLevel.FACULTY and venue.owning_faculty:
                return venue.owning_faculty.school_id == admin_prof.scope_school.id
            elif venue.owning_level == Venue.OwningLevel.DEPARTMENT and venue.owning_department:
                return venue.owning_department.faculty.school_id == admin_prof.scope_school.id
            return False

    return False


def determine_booking_routing(
    user,
    venue,
    date_or_start_date,
    start_time,
    end_time,
    entry_type="lecture",
    course=None,
    academic_session="2025/2026",
    recurrence_rule=None,
    recurrence_end_date=None,
    lecturer_ids=None,
    invigilator_ids=None,
    exclude_entry_id=None,
):
    """
    Orchestrates scope validation and conflict checking to determine 1 of 3 outcomes:
    1. 'PROCEED': Requester has scope authority AND no clashes exist.
    2. 'HARD_REJECT': Requester has scope authority BUT clashes exist.
    3. 'ROUTE_APPROVAL': Venue is outside requester's scope (routes for approval).
    """
    has_scope = is_venue_within_user_scope(user, venue)

    # 1. Collect all conflicts
    all_conflicts = []

    # Venue clashes
    venue_conflicts = check_venue_overlap(
        venue=venue,
        date=date_or_start_date,
        start_time=start_time,
        end_time=end_time,
        recurrence_rule=recurrence_rule,
        recurrence_start_date=date_or_start_date,
        recurrence_end_date=recurrence_end_date,
        exclude_entry_id=exclude_entry_id,
    )
    all_conflicts.extend(venue_conflicts)

    # Student exam clashes (if exam)
    if entry_type == "exam" and course:
        student_conflicts = check_student_exam_clash(
            course=course,
            date=date_or_start_date,
            start_time=start_time,
            end_time=end_time,
            academic_session=academic_session,
            exclude_entry_id=exclude_entry_id,
        )
        all_conflicts.extend(student_conflicts)

    # Lecturer clashes
    all_staff_ids = set(lecturer_ids or []) | set(invigilator_ids or [])
    if all_staff_ids:
        lecturer_conflicts = check_lecturer_clash(
            lecturer_ids=list(all_staff_ids),
            date=date_or_start_date,
            start_time=start_time,
            end_time=end_time,
            exclude_entry_id=exclude_entry_id,
        )
        all_conflicts.extend(lecturer_conflicts)

    # Resolve outcome
    if not has_scope:
        # Route to venue's owning admin
        owning_admin = None
        if venue.owning_level == Venue.OwningLevel.DEPARTMENT and venue.owning_department:
            owning_admin = AdminOfficer.objects.filter(level="department", scope_department=venue.owning_department).first()
        elif venue.owning_level == Venue.OwningLevel.FACULTY and venue.owning_faculty:
            owning_admin = AdminOfficer.objects.filter(level="faculty", scope_faculty=venue.owning_faculty).first()
        elif venue.owning_level == Venue.OwningLevel.SCHOOL and venue.owning_school:
            owning_admin = AdminOfficer.objects.filter(level="school", scope_school=venue.owning_school).first()

        return {
            "outcome": "ROUTE_APPROVAL",
            "routed_to_admin_id": owning_admin.id if owning_admin else None,
            "conflicts": all_conflicts,
            "message": "Booking touches a venue outside your direct scope and has been routed for approval.",
        }

    if all_conflicts:
        return {
            "outcome": "HARD_REJECT",
            "conflicts": all_conflicts,
            "message": f"Booking clashes with {len(all_conflicts)} existing schedule entry/duty.",
        }

    return {
        "outcome": "PROCEED",
        "conflicts": [],
        "message": "No conflicts detected. Booking permitted.",
    }
