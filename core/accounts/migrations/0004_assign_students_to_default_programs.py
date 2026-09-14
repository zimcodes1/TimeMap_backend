from django.db import migrations


def assign_students_to_default_programs(apps, schema_editor):
    Student = apps.get_model("accounts", "Student")
    Program = apps.get_model("hierarchy", "Program")

    for student in Student.objects.filter(program__isnull=True, department__isnull=False):
        default_program = Program.objects.filter(department=student.department, is_default=True).first()
        if not default_program:
            # If no is_default=True program exists, fallback to first program or create one
            default_program = Program.objects.filter(department=student.department).first()
        if default_program:
            student.program = default_program
            student.save(update_fields=["program"])


def reverse_assignment(apps, schema_editor):
    Student = apps.get_model("accounts", "Student")
    Student.objects.update(program=None)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_student_program"),
        ("hierarchy", "0004_create_default_programs"),
    ]

    operations = [
        migrations.RunPython(assign_students_to_default_programs, reverse_assignment),
    ]
