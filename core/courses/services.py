from django.db.models import Q
from .models import Course, CourseAccessGrant


def get_visible_courses_for_student(student):
    """
    Returns a queryset of Course objects visible to a student.
    Visiblity rules:
    1. Default ownership:
       - 'department': student's home department matches course.owning_department
       - 'faculty': student's faculty matches course.owning_faculty
       - 'school': student's school matches course.owning_school
       - 'general': visible to everyone
    2. Approved access grants:
       - 'approved' CourseAccessGrant granted to student's department, faculty, or school.
    """
    if not student or not hasattr(student, "department"):
        return Course.objects.none()

    dept = student.department
    fac = dept.faculty
    sch = fac.school

    # 1. Default ownership matches
    default_q = (
        Q(owning_level=Course.OwningLevel.GENERAL)
        | Q(owning_level=Course.OwningLevel.DEPARTMENT, owning_department=dept)
        | Q(owning_level=Course.OwningLevel.FACULTY, owning_faculty=fac)
        | Q(owning_level=Course.OwningLevel.SCHOOL, owning_school=sch)
    )

    # 2. Approved grants
    approved_grant_course_ids = CourseAccessGrant.objects.filter(
        status=CourseAccessGrant.Status.APPROVED
    ).filter(
        Q(granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT, granted_to_department=dept)
        | Q(granted_to_level=CourseAccessGrant.GrantedToLevel.FACULTY, granted_to_faculty=fac)
        | Q(granted_to_level=CourseAccessGrant.GrantedToLevel.SCHOOL, granted_to_school=sch)
    ).values_list("course_id", flat=True)

    return Course.objects.filter(default_q | Q(id__in=approved_grant_course_ids)).distinct()
