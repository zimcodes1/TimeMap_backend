import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student
from accounts.permissions import get_user_scope_departments
from courses.models import Course
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from scheduling.models import LectureSession

from .models import AnalyticsQueryLog, CourseLectureSummarySnapshot


def _parse_date(date_str):
    if not date_str:
        return None
    if isinstance(date_str, datetime.date):
        return date_str
    try:
        return datetime.datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except ValueError:
        raise serializers.ValidationError({"detail": f"Invalid date format '{date_str}'. Use YYYY-MM-DD."})


def get_class_rep_analytics(student_user, start_date=None, end_date=None):
    """
    Delivers lecture hold analytics for Class Representatives.
    Constrained to sessions in their department and level within start_date/end_date.
    """
    if not hasattr(student_user, "student_profile"):
        raise serializers.ValidationError({"detail": "Only student accounts can access class rep analytics."})

    student = student_user.student_profile
    if not student.is_class_rep:
        raise serializers.ValidationError({"detail": "Only designated Class Representatives can access this endpoint."})

    start_d = _parse_date(start_date)
    end_d = _parse_date(end_date)

    # Scoped to student's department and level
    sessions = LectureSession.objects.filter(
        timetable_entry__course__owning_department=student.department,
        timetable_entry__course__level=student.level,
    )

    if start_d:
        sessions = sessions.filter(session_date__gte=start_d)
    if end_d:
        sessions = sessions.filter(session_date__lte=end_d)

    total_sessions = sessions.count()
    held_count = sessions.filter(
        Q(status=LectureSession.Status.HELD) | Q(report__held=True)
    ).distinct().count()
    not_held_count = sessions.filter(
        Q(status=LectureSession.Status.NOT_HELD) | Q(report__held=False)
    ).distinct().count()
    cancelled_count = sessions.filter(status=LectureSession.Status.CANCELLED).count()

    hold_rate = round((held_count / total_sessions) * 100, 2) if total_sessions > 0 else 0.0

    # Course breakdown
    course_map = {}
    for s in sessions.select_related("timetable_entry__course"):
        course = s.timetable_entry.course if s.timetable_entry else None
        if not course:
            continue

        cid = course.id
        if cid not in course_map:
            course_map[cid] = {
                "course_id": cid,
                "course_code": course.code,
                "course_title": course.title,
                "total_sessions": 0,
                "held_count": 0,
                "not_held_count": 0,
                "cancelled_count": 0,
            }
        
        course_map[cid]["total_sessions"] += 1
        if s.status == LectureSession.Status.HELD or (hasattr(s, "report") and s.report.held):
            course_map[cid]["held_count"] += 1
        elif s.status == LectureSession.Status.NOT_HELD or (hasattr(s, "report") and not s.report.held):
            course_map[cid]["not_held_count"] += 1
        elif s.status == LectureSession.Status.CANCELLED:
            course_map[cid]["cancelled_count"] += 1

    course_breakdown = list(course_map.values())
    for item in course_breakdown:
        tot = item["total_sessions"]
        h = item["held_count"]
        item["hold_rate_percentage"] = round((h / tot) * 100, 2) if tot > 0 else 0.0

    # Log query
    AnalyticsQueryLog.objects.create(
        user=student_user,
        query_type="class_rep",
        start_date=start_d,
        end_date=end_d,
    )

    return {
        "student_info": {
            "full_name": student.full_name,
            "department": student.department.name if student.department else "",
            "level": student.level,
        },
        "query_range": {
            "start_date": start_d,
            "end_date": end_d,
        },
        "summary": {
            "total_sessions": total_sessions,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "cancelled_count": cancelled_count,
            "hold_rate_percentage": hold_rate,
        },
        "course_breakdown": course_breakdown,
    }


def get_lecturer_analytics(lecturer_user, start_date=None, end_date=None, course_id=None):
    """
    Delivers lecture hold analytics for Lecturers.
    Can view overall lectures held within date range across assigned courses,
    or filtered to a specific assigned course.
    """
    if not hasattr(lecturer_user, "lecturer_profile"):
        raise serializers.ValidationError({"detail": "Only lecturer accounts can access lecturer analytics."})

    lecturer = lecturer_user.lecturer_profile
    assigned_courses = Course.objects.filter(lecturers=lecturer)

    start_d = _parse_date(start_date)
    end_d = _parse_date(end_date)

    target_course = None
    if course_id:
        target_course = assigned_courses.filter(id=course_id).first()
        if not target_course:
            raise serializers.ValidationError({"detail": f"You are not assigned as a lecturer for course ID {course_id}."})

    sessions = LectureSession.objects.filter(
        timetable_entry__course__in=assigned_courses if not target_course else [target_course]
    )

    if start_d:
        sessions = sessions.filter(session_date__gte=start_d)
    if end_d:
        sessions = sessions.filter(session_date__lte=end_d)

    total_sessions = sessions.count()
    held_count = sessions.filter(
        Q(status=LectureSession.Status.HELD) | Q(report__held=True)
    ).distinct().count()
    not_held_count = sessions.filter(
        Q(status=LectureSession.Status.NOT_HELD) | Q(report__held=False)
    ).distinct().count()
    cancelled_count = sessions.filter(status=LectureSession.Status.CANCELLED).count()

    hold_rate = round((held_count / total_sessions) * 100, 2) if total_sessions > 0 else 0.0

    # Per course breakdown
    course_map = {}
    for c in assigned_courses if not target_course else [target_course]:
        course_map[c.id] = {
            "course_id": c.id,
            "course_code": c.code,
            "course_title": c.title,
            "total_sessions": 0,
            "held_count": 0,
            "not_held_count": 0,
            "cancelled_count": 0,
        }

    for s in sessions.select_related("timetable_entry__course"):
        course = s.timetable_entry.course if s.timetable_entry else None
        if not course or course.id not in course_map:
            continue

        cid = course.id
        course_map[cid]["total_sessions"] += 1
        if s.status == LectureSession.Status.HELD or (hasattr(s, "report") and s.report.held):
            course_map[cid]["held_count"] += 1
        elif s.status == LectureSession.Status.NOT_HELD or (hasattr(s, "report") and not s.report.held):
            course_map[cid]["not_held_count"] += 1
        elif s.status == LectureSession.Status.CANCELLED:
            course_map[cid]["cancelled_count"] += 1

    course_breakdown = list(course_map.values())
    for item in course_breakdown:
        tot = item["total_sessions"]
        h = item["held_count"]
        item["hold_rate_percentage"] = round((h / tot) * 100, 2) if tot > 0 else 0.0

    # Log query
    AnalyticsQueryLog.objects.create(
        user=lecturer_user,
        query_type="lecturer",
        start_date=start_d,
        end_date=end_d,
        target_course=target_course,
        target_lecturer=lecturer,
    )

    return {
        "lecturer_info": {
            "full_name": lecturer.full_name,
            "staff_id": lecturer.staff_id,
            "department": lecturer.department.name if lecturer.department else "",
        },
        "query_range": {
            "start_date": start_d,
            "end_date": end_d,
            "filtered_course": target_course.code if target_course else None,
        },
        "summary": {
            "total_sessions": total_sessions,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "cancelled_count": cancelled_count,
            "hold_rate_percentage": hold_rate,
        },
        "course_breakdown": course_breakdown,
    }


def get_admin_analytics(admin_user, start_date=None, end_date=None, lecturer_id=None, course_id=None):
    """
    Delivers analytics for Admin Officers.
    Can view analytics per lecturer, per course assigned to a lecturer, or across their administrative scope.
    """
    if not hasattr(admin_user, "admin_profile"):
        raise serializers.ValidationError({"detail": "Only admin accounts can access admin analytics."})

    admin = admin_user.admin_profile
    dept_qs = get_user_scope_departments(admin_user)

    start_d = _parse_date(start_date)
    end_d = _parse_date(end_date)

    target_lecturer = None
    if lecturer_id:
        target_lecturer = LecturerStaff.objects.filter(id=lecturer_id, department__in=dept_qs).first()
        if not target_lecturer:
            raise serializers.ValidationError({"detail": f"Lecturer ID {lecturer_id} not found within your administrative scope."})

    target_course = None
    if course_id:
        target_course = Course.objects.filter(id=course_id, owning_department__in=dept_qs).first()
        if not target_course:
            raise serializers.ValidationError({"detail": f"Course ID {course_id} not found within your administrative scope."})

    sessions = LectureSession.objects.filter(
        timetable_entry__course__owning_department__in=dept_qs
    )

    if target_lecturer:
        sessions = sessions.filter(timetable_entry__course__lecturers=target_lecturer)

    if target_course:
        sessions = sessions.filter(timetable_entry__course=target_course)

    if start_d:
        sessions = sessions.filter(session_date__gte=start_d)
    if end_d:
        sessions = sessions.filter(session_date__lte=end_d)

    total_sessions = sessions.count()
    held_count = sessions.filter(
        Q(status=LectureSession.Status.HELD) | Q(report__held=True)
    ).distinct().count()
    not_held_count = sessions.filter(
        Q(status=LectureSession.Status.NOT_HELD) | Q(report__held=False)
    ).distinct().count()
    cancelled_count = sessions.filter(status=LectureSession.Status.CANCELLED).count()

    hold_rate = round((held_count / total_sessions) * 100, 2) if total_sessions > 0 else 0.0

    # Per lecturer breakdown
    lecturers_in_scope = LecturerStaff.objects.filter(department__in=dept_qs)
    if target_lecturer:
        lecturers_in_scope = lecturers_in_scope.filter(id=target_lecturer.id)

    lecturer_map = {}
    for lec in lecturers_in_scope:
        lecturer_map[lec.id] = {
            "lecturer_id": lec.id,
            "staff_id": lec.staff_id,
            "full_name": lec.full_name,
            "total_sessions": 0,
            "held_count": 0,
            "not_held_count": 0,
            "cancelled_count": 0,
        }

    for s in sessions.prefetch_related("timetable_entry__course__lecturers"):
        course = s.timetable_entry.course if s.timetable_entry else None
        if not course:
            continue

        for lec in course.lecturers.all():
            if lec.id in lecturer_map:
                lecturer_map[lec.id]["total_sessions"] += 1
                if s.status == LectureSession.Status.HELD or (hasattr(s, "report") and s.report.held):
                    lecturer_map[lec.id]["held_count"] += 1
                elif s.status == LectureSession.Status.NOT_HELD or (hasattr(s, "report") and not s.report.held):
                    lecturer_map[lec.id]["not_held_count"] += 1
                elif s.status == LectureSession.Status.CANCELLED:
                    lecturer_map[lec.id]["cancelled_count"] += 1

    lecturer_breakdown = list(lecturer_map.values())
    for item in lecturer_breakdown:
        tot = item["total_sessions"]
        h = item["held_count"]
        item["hold_rate_percentage"] = round((h / tot) * 100, 2) if tot > 0 else 0.0

    # Log query
    AnalyticsQueryLog.objects.create(
        user=admin_user,
        query_type="admin",
        start_date=start_d,
        end_date=end_d,
        target_course=target_course,
        target_lecturer=target_lecturer,
    )

    return {
        "admin_info": {
            "full_name": admin.full_name,
            "level": admin.level,
        },
        "query_range": {
            "start_date": start_d,
            "end_date": end_d,
            "filtered_lecturer": target_lecturer.full_name if target_lecturer else None,
            "filtered_course": target_course.code if target_course else None,
        },
        "summary": {
            "total_sessions": total_sessions,
            "held_count": held_count,
            "not_held_count": not_held_count,
            "cancelled_count": cancelled_count,
            "hold_rate_percentage": hold_rate,
        },
        "lecturer_breakdown": lecturer_breakdown,
    }
