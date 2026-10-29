"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Education (EDU) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Education (EDU) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Education (EDU) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="EDU").first()
            if not faculty:
                self.stderr.write("Faculty EDU not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            populations = {
                # Educational Foundations (EDF)
                "EDFGEN": {100: 140, 200: 115, 300: 95, 400: 80},
                "EDFECE": {100: 75, 200: 60, 300: 50, 400: 40},

                # Science, Technology and Mathematics Education (STM)
                "STMGEN": {100: 100, 200: 80, 300: 65, 400: 50},
                "STMCMP": {100: 85, 200: 70, 300: 55, 400: 45},
                "STMMTH": {100: 70, 200: 55, 300: 45, 400: 35},
                "STMCHM": {100: 65, 200: 50, 300: 40, 400: 30},
                "STMPHY": {100: 60, 200: 45, 300: 35, 400: 25},

                # Arts and Social Science Education (ASE)
                "ASEGEN": {100: 110, 200: 90, 300: 75, 400: 60},
                "ASEECO": {100: 85, 200: 70, 300: 55, 400: 45},
                "ASESOC": {100: 80, 200: 65, 300: 50, 400: 40},

                # Guidance and Counselling (GAC)
                "GACGEN": {100: 120, 200: 100, 300: 80, 400: 65},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Education Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

