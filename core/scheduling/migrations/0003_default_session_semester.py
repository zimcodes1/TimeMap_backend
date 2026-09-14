import datetime
from django.db import migrations


def create_default_sessions_and_semesters(apps, schema_editor):
    School = apps.get_model("hierarchy", "School")
    AcademicSession = apps.get_model("scheduling", "AcademicSession")
    Semester = apps.get_model("scheduling", "Semester")
    TimetableEntry = apps.get_model("scheduling", "TimetableEntry")
    Course = apps.get_model("courses", "Course")

    today = datetime.date.today()
    start_of_year = datetime.date(today.year, 1, 1)
    end_of_year = datetime.date(today.year, 12, 31)

    for school in School.objects.all():
        session, _ = AcademicSession.objects.get_or_create(
            school=school,
            label=f"{today.year}/{today.year + 1}",
            defaults={
                "start_date": start_of_year,
                "end_date": end_of_year,
                "is_current": True,
            },
        )
        semester, _ = Semester.objects.get_or_create(
            session=session,
            name="first",
            defaults={
                "start_date": start_of_year,
                "end_date": end_of_year,
                "is_active": True,
            },
        )

        # Link timetable entries belonging to this school
        for entry in TimetableEntry.objects.filter(semester__isnull=True):
            entry_school = None
            if entry.venue:
                if entry.venue.owning_school:
                    entry_school = entry.venue.owning_school
                elif entry.venue.owning_department and entry.venue.owning_department.faculty:
                    entry_school = entry.venue.owning_department.faculty.school
                elif entry.venue.owning_faculty:
                    entry_school = entry.venue.owning_faculty.school
            elif entry.course:
                if entry.course.owning_school:
                    entry_school = entry.course.owning_school
                elif entry.course.owning_faculty:
                    entry_school = entry.course.owning_faculty.school
                elif entry.course.owning_department and entry.course.owning_department.faculty:
                    entry_school = entry.course.owning_department.faculty.school

            if entry_school == school:
                entry.semester = semester
                entry.save(update_fields=["semester"])

        # Link courses belonging to this school
        for course in Course.objects.filter(semester__isnull=True):
            course_school = None
            if course.owning_school:
                course_school = course.owning_school
            elif course.owning_faculty:
                course_school = course.owning_faculty.school
            elif course.owning_department and course.owning_department.faculty:
                course_school = course.owning_department.faculty.school

            if course_school == school:
                course.semester = semester
                course.save(update_fields=["semester"])


def reverse_sessions_and_semesters(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0002_course_semester_program"),
        ("hierarchy", "0004_create_default_programs"),
        ("scheduling", "0002_academic_session_semester"),
    ]

    operations = [
        migrations.RunPython(create_default_sessions_and_semesters, reverse_sessions_and_semesters),
    ]
