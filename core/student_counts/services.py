from django.db.models import Sum

from .models import DepartmentStudentCount


def get_student_count_analytics(queryset, admin_level):
    """Return only analytics dimensions appropriate to the requesting admin tier."""
    total_students = queryset.aggregate(total=Sum("count"))["total"] or 0
    department_breakdown = list(queryset.values(
        "department_id", "department__name", "department__code",
        "department__faculty_id", "department__faculty__name",
        "department__faculty__school_id", "department__faculty__school__name",
    ).annotate(student_count=Sum("count")).order_by("department__name"))
    faculty_breakdown = list(queryset.values(
        "department__faculty_id", "department__faculty__name",
    ).annotate(student_count=Sum("count")).order_by("department__faculty__name"))
    school_breakdown = list(queryset.values(
        "department__faculty__school_id", "department__faculty__school__name",
    ).annotate(student_count=Sum("count")).order_by("department__faculty__school__name"))
    level_breakdown = list(queryset.values("level").annotate(student_count=Sum("count")).order_by("level"))

    response = {
        "summary": {
            "total_students": total_students,
            "levels_reporting": queryset.values("level").distinct().count(),
        },
        "available_dimensions": ["level"],
        "by_department": [],
        "by_faculty": [],
        "by_school": [],
        "by_level": [
            {"level": row["level"], "student_count": row["student_count"]}
            for row in level_breakdown
        ],
    }

    if admin_level in ("faculty", "school", "university"):
        response["summary"]["departments_reporting"] = len(department_breakdown)
        response["available_dimensions"].append("department")
        response["by_department"] = [
            {
                "department_id": row["department_id"], "department_name": row["department__name"],
                "department_code": row["department__code"], "faculty_id": row["department__faculty_id"],
                "faculty_name": row["department__faculty__name"], "school_id": row["department__faculty__school_id"],
                "school_name": row["department__faculty__school__name"], "student_count": row["student_count"],
            } for row in department_breakdown
        ]
    if admin_level in ("school", "university"):
        response["available_dimensions"].append("faculty")
        response["by_faculty"] = [
            {"faculty_id": row["department__faculty_id"], "faculty_name": row["department__faculty__name"], "student_count": row["student_count"]}
            for row in faculty_breakdown
        ]
    if admin_level == "university":
        response["available_dimensions"].append("school")
        response["by_school"] = [
            {"school_id": row["department__faculty__school_id"], "school_name": row["department__faculty__school__name"], "student_count": row["student_count"]}
            for row in school_breakdown
        ]
    return response
