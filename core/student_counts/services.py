from django.db.models import Sum

from .models import ProgramStudentCount


def get_student_count_analytics(queryset, admin_level):
    """Return only analytics dimensions appropriate to the requesting admin tier."""
    total_students = queryset.aggregate(total=Sum("count"))["total"] or 0
    level_breakdown = list(queryset.values("level").annotate(student_count=Sum("count")).order_by("level"))

    response = {
        "summary": {
            "total_students": total_students,
            "levels_reporting": queryset.values("level").distinct().count(),
        },
        "available_dimensions": ["level"],
        "by_program": [],
        "by_department": [],
        "by_faculty": [],
        "by_school": [],
        "by_level": [
            {"level": row["level"], "student_count": row["student_count"]}
            for row in level_breakdown
        ],
    }

    if admin_level == "department":
        # Department admins see breakdown by program
        program_breakdown = list(queryset.values(
            "program_id", "program__name", "program__code",
        ).annotate(student_count=Sum("count")).order_by("program__name"))
        response["summary"]["programs_reporting"] = len(program_breakdown)
        response["available_dimensions"].append("program")
        response["by_program"] = [
            {
                "program_id": row["program_id"],
                "program_name": row["program__name"],
                "program_code": row["program__code"],
                "student_count": row["student_count"],
            }
            for row in program_breakdown
        ]
    elif admin_level == "faculty":
        department_breakdown = list(queryset.values(
            "program__department_id", "program__department__name", "program__department__code",
            "program__department__faculty_id", "program__department__faculty__name",
            "program__department__faculty__school_id", "program__department__faculty__school__name",
        ).annotate(student_count=Sum("count")).order_by("program__department__name"))
        response["summary"]["departments_reporting"] = len(department_breakdown)
        response["available_dimensions"].append("department")
        response["by_department"] = [
            {
                "department_id": row["program__department_id"],
                "department_name": row["program__department__name"],
                "department_code": row["program__department__code"],
                "faculty_id": row["program__department__faculty_id"],
                "faculty_name": row["program__department__faculty__name"],
                "school_id": row["program__department__faculty__school_id"],
                "school_name": row["program__department__faculty__school__name"],
                "student_count": row["student_count"],
            }
            for row in department_breakdown
        ]
    elif admin_level == "school":
        faculty_breakdown = list(queryset.values(
            "program__department__faculty_id", "program__department__faculty__name",
        ).annotate(student_count=Sum("count")).order_by("program__department__faculty__name"))
        response["summary"]["faculties_reporting"] = len(faculty_breakdown)
        response["available_dimensions"].append("faculty")
        response["by_faculty"] = [
            {
                "faculty_id": row["program__department__faculty_id"],
                "faculty_name": row["program__department__faculty__name"],
                "student_count": row["student_count"],
            }
            for row in faculty_breakdown
        ]
    elif admin_level == "university":
        school_breakdown = list(queryset.values(
            "program__department__faculty__school_id", "program__department__faculty__school__name",
        ).annotate(student_count=Sum("count")).order_by("program__department__faculty__school__name"))
        response["summary"]["schools_reporting"] = len(school_breakdown)
        response["available_dimensions"].append("school")
        response["by_school"] = [
            {
                "school_id": row["program__department__faculty__school_id"],
                "school_name": row["program__department__faculty__school__name"],
                "student_count": row["student_count"],
            }
            for row in school_breakdown
        ]

    return response
