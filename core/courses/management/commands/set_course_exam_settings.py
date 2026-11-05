"""Management command to configure exam settings for seeded/existing courses.

Rules:
- Non-final levels (< 400L or < department/program max_level):
    - exam_type = 'cbt'
    - exam_duration_per_student_minutes = 30
    - exam_duration_minutes = None
- Final level (400L in most cases, or >= max_level):
    - exam_type = 'written'
    - exam_duration_minutes = 120 (2 hours)
    - exam_duration_per_student_minutes = None
"""

from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course
from hierarchy.models import Faculty, Department


def resolve_course_final_level(course: Course) -> int:
    """Determine the final level threshold for a course."""
    if course.target_program and course.target_program.max_level:
        return course.target_program.max_level
    if course.owning_department and course.owning_department.computed_max_level:
        return course.owning_department.computed_max_level

    # Check approved course access grants if faculty or school owned
    grants = course.access_grants.filter(status="approved").select_related(
        "target_program", "granted_to_department"
    )
    max_levels = []
    for g in grants:
        if g.target_program and g.target_program.max_level:
            max_levels.append(g.target_program.max_level)
        elif g.granted_to_department and g.granted_to_department.computed_max_level:
            max_levels.append(g.granted_to_department.computed_max_level)
    if max_levels:
        return max(max_levels)

    # Default institutional final level is 400L
    return 400


class Command(BaseCommand):
    help = (
        "Converts seeded courses to CBT (30 mins/student) for non-final levels (100L-300L) "
        "and Written (120 mins) for final levels (400L+)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the changes without committing to the database.",
        )
        parser.add_argument(
            "--faculty",
            type=str,
            help="Filter courses by faculty code (e.g. FNAS).",
        )
        parser.add_argument(
            "--department",
            type=str,
            help="Filter courses by department code (e.g. CMP).",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        faculty_code = options.get("faculty")
        dept_code = options.get("department")

        courses = Course.objects.all().select_related(
            "target_program", "owning_department", "owning_faculty"
        ).prefetch_related("access_grants__target_program", "access_grants__granted_to_department")

        if faculty_code:
            courses = courses.filter(owning_faculty__code=faculty_code)
        if dept_code:
            courses = courses.filter(owning_department__code=dept_code)

        total_courses = courses.count()
        if total_courses == 0:
            self.stdout.write(self.style.WARNING("No courses found matching criteria."))
            return

        self.stdout.write(
            f"Processing {total_courses} courses (dry_run={dry_run})...\n"
        )

        cbt_count = 0
        written_count = 0
        level_stats = defaultdict(lambda: {"cbt": 0, "written": 0})
        courses_to_update = []

        for course in courses:
            final_level = resolve_course_final_level(course)
            is_final = (course.level >= final_level) or (course.level >= 400)

            if is_final:
                new_exam_type = Course.ExamType.WRITTEN
                new_duration_minutes = 120
                new_per_student = None
                written_count += 1
                level_stats[course.level]["written"] += 1
            else:
                new_exam_type = Course.ExamType.CBT
                new_duration_minutes = None
                new_per_student = 30
                cbt_count += 1
                level_stats[course.level]["cbt"] += 1

            course.exam_type = new_exam_type
            course.exam_duration_minutes = new_duration_minutes
            course.exam_duration_per_student_minutes = new_per_student
            courses_to_update.append(course)

        if not dry_run:
            with transaction.atomic():
                Course.objects.bulk_update(
                    courses_to_update,
                    ["exam_type", "exam_duration_minutes", "exam_duration_per_student_minutes"],
                    batch_size=200,
                )
            self.stdout.write(self.style.SUCCESS("Database successfully updated!"))
        else:
            self.stdout.write(self.style.NOTICE("Dry run complete. No database changes written."))

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("EXAM SETTINGS CONVERSION SUMMARY")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total courses processed: {len(courses_to_update)}")
        self.stdout.write(
            f"- Converted to CBT (30m per student): {cbt_count}"
        )
        self.stdout.write(
            f"- Converted to Written (120m nominal): {written_count}"
        )
        self.stdout.write("\nBreakdown by Level:")
        for lvl in sorted(level_stats.keys()):
            stats = level_stats[lvl]
            self.stdout.write(
                f"  • {lvl} Level: {stats['cbt']} CBT (30m/student) | {stats['written']} Written (2 hrs)"
            )
        self.stdout.write("=" * 50)
