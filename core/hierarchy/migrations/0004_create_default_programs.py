from django.db import migrations


def create_default_programs(apps, schema_editor):
    """
    For each existing Department that doesn't yet have a default Program,
    create one with the same name and max_level.
    """
    Department = apps.get_model("hierarchy", "Department")
    Program = apps.get_model("hierarchy", "Program")

    for dept in Department.objects.all():
        if not Program.objects.filter(department=dept, is_default=True).exists():
            Program.objects.create(
                department=dept,
                name=dept.name,
                code=f"{dept.code}GEN",
                max_level=dept.max_level,
                is_default=True,
            )


def reverse_default_programs(apps, schema_editor):
    """Remove auto-created default programs."""
    Program = apps.get_model("hierarchy", "Program")
    Program.objects.filter(is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hierarchy", "0003_program"),
    ]

    operations = [
        migrations.RunPython(create_default_programs, reverse_default_programs),
    ]
