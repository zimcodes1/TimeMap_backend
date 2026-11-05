"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Environmental Science (ENV) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Environmental Science (ENV) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Environmental Science (ENV) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENV").first()
            if not faculty:
                self.stderr.write("Faculty ENV not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            populations = {
                # Architecture (ARC) - 5-year curriculum
                "ARCGEN": {100: 90, 200: 80, 300: 70, 400: 60, 500: 50},

                # Geography and Environmental Management (GEO) - 4-year curriculum
                "GEOGEN": {100: 140, 200: 115, 300: 95, 400: 80},
                "GEOENV": {100: 80, 200: 65, 300: 50, 400: 40},

                # Urban and Regional Planning (URP) - 5-year curriculum
                "URPGEN": {100: 80, 200: 70, 300: 60, 400: 50, 500: 40},

                # Estate Management (ESM) - 5-year curriculum
                "ESMGEN": {100: 95, 200: 80, 300: 70, 400: 60, 500: 50},

                # Quantity Surveying (QTS) - 5-year curriculum
                "QTSGEN": {100: 90, 200: 75, 300: 65, 400: 55, 500: 45},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Environmental Science Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

