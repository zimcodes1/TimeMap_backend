import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student
from django.utils import timezone
from rest_framework import serializers
from scheduling.models import LectureSession

from .models import ClassRepReport, UnreportedSessionFlag


def calculate_report_window_expiry(session, window_minutes=30, window_hours=None):
    """
    Calculates window_expires_at for a LectureSession (session_date + session_end_time + window_minutes).
    Defaults to 30 minutes after the lecture ends.
    """
    if window_hours is not None:
        window_minutes = int(window_hours * 60)
    tz = timezone.get_current_timezone()
    dt = datetime.datetime.combine(session.session_date, session.session_end_time)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, tz)
    return dt + datetime.timedelta(minutes=window_minutes)


def create_class_rep_report(student_user, session, held, reason, window_minutes=30, window_hours=None):
    """
    Validates class rep eligibility, department scope, and server-side reporting window expiration before creating report.
    Reporting window is open during the lecture (from session_start_time) and up to 30 minutes after (session_end_time + 30m).
    """
    if not hasattr(student_user, "student_profile"):
        raise serializers.ValidationError({"detail": "Only students can submit class rep reports."})

    student = student_user.student_profile
    if not student.is_class_rep:
        raise serializers.ValidationError({"detail": "Only designated Class Representatives can submit lecture reports."})

    # Department scope check
    course_dept = session.timetable_entry.course.owning_department if session.timetable_entry and session.timetable_entry.course else None
    if course_dept and student.department_id != course_dept.id:
        raise serializers.ValidationError({"detail": "Class Representatives can only report on sessions in their own department."})

    # Reason handling: required if not held, optional with default if held
    reason_clean = (reason or "").strip()
    if held and not reason_clean:
        reason_clean = "Lecture held as scheduled"
    elif not held and not reason_clean:
        raise serializers.ValidationError({"reason": "A reason is required when a lecture was not held."})

    # Server-side reporting window enforcement
    tz = timezone.get_current_timezone()
    now = timezone.now()
    start_dt = datetime.datetime.combine(session.session_date, session.session_start_time)
    if timezone.is_naive(start_dt):
        start_dt = timezone.make_aware(start_dt, tz)

    if now < start_dt:
        raise serializers.ValidationError({"detail": "Reporting is only allowed during or up to 30 minutes after the lecture."})

    expiry = calculate_report_window_expiry(session, window_minutes=window_minutes, window_hours=window_hours)
    if now > expiry:
        raise serializers.ValidationError({"detail": f"Reporting window for this session expired at {expiry.strftime('%Y-%m-%d %H:%M:%S')}."})

    # Check if already reported
    if hasattr(session, "report"):
        raise serializers.ValidationError({"detail": "This lecture session has already been reported."})

    report = ClassRepReport.objects.create(
        lecture_session=session,
        reported_by=student,
        held=held,
        reason=reason_clean,
        window_expires_at=expiry,
    )

    # Update session status based on report
    session.status = LectureSession.Status.HELD if held else LectureSession.Status.NOT_HELD
    session.save()

    return report


def run_unreported_sessions_sweep(window_hours=2):
    """
    Identifies expired sessions that have passed their reporting window without a report or flag,
    and creates UnreportedSessionFlag records.
    """
    now = timezone.now()
    # Find sessions whose end time + window_hours is in the past
    sessions = LectureSession.objects.filter(
        status=LectureSession.Status.SCHEDULED,
        report__isnull=True,
        unreported_flag__isnull=True,
    )

    flagged_count = 0
    for session in sessions:
        expiry = calculate_report_window_expiry(session, window_hours=window_hours)
        if now > expiry:
            flag = UnreportedSessionFlag.objects.create(lecture_session=session)
            flagged_count += 1

            # Notify department admins
            dept = session.timetable_entry.course.owning_department if session.timetable_entry and session.timetable_entry.course else None
            if dept:
                admins = AdminOfficer.objects.filter(level="department", scope_department=dept)
                for admin in admins:
                    try:
                        from notifications.models import Notification
                        from notifications.services import dispatch_event_notification
                        dispatch_event_notification(
                            recipient=admin.user,
                            notification_type=Notification.NotificationType.SESSION_UNREPORTED,
                            title="Unreported Lecture Session",
                            body=f"Session for '{session.timetable_entry.title}' on {session.session_date} was not reported within window.",
                            related_model="UnreportedSessionFlag",
                            related_id=flag.id,
                        )
                    except Exception:
                        pass

    return flagged_count


def acknowledge_unreported_flag(flag, admin_user):
    """
    Marks an UnreportedSessionFlag as acknowledged by an AdminOfficer.
    """
    if not hasattr(admin_user, "admin_profile"):
        raise serializers.ValidationError({"detail": "Only Admin Officers can acknowledge unreported session flags."})

    admin_prof = admin_user.admin_profile
    flag.acknowledged_by = admin_prof
    flag.acknowledged_at = timezone.now()
    flag.save()
    return flag


def submit_lecturer_response(report, lecturer_user, response_text):
    """
    Attaches a lecturer dispute/response to a ClassRepReport.
    Validates that the lecturer is assigned to the course.
    """
    if not hasattr(lecturer_user, "lecturer_profile"):
        raise serializers.ValidationError({"detail": "Only assigned lecturers can respond to reports."})

    lecturer = lecturer_user.lecturer_profile
    course = report.lecture_session.timetable_entry.course if report.lecture_session and report.lecture_session.timetable_entry else None

    if course and not course.lecturers.filter(id=lecturer.id).exists():
        raise serializers.ValidationError({"detail": "You are not assigned as a lecturer for this course."})

    report.lecturer_response = response_text
    report.lecturer_responded_at = timezone.now()
    report.save()
    return report
