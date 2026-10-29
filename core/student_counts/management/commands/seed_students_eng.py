"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Engineering (ENG) at NSUK (5-year curriculum).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Engineering (ENG) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Engineering (ENG) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENG").first()
            if not faculty:
                self.stderr.write("Faculty ENG not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            # 5-year B.Eng Programs (100L - 500L)
            populations = {
                # Civil Engineering (CVE)
                "CVEGEN": {100: 130, 200: 115, 300: 100, 400: 90, 500: 80},
                "CVEWTR": {100: 60, 200: 50, 300: 45, 400: 40, 500: 35},

                # Electrical and Electronics Engineering (EEE)
                "EEEGEN": {100: 140, 200: 120, 300: 105, 400: 95, 500: 85},
                "EEETEL": {100: 65, 200: 55, 300: 50, 400: 45, 500: 40},

                # Mechanical Engineering (MEE)
                "MEEGEN": {100: 135, 200: 115, 300: 100, 400: 90, 500: 80},
                "MEEAUT": {100: 65, 200: 55, 300: 45, 400: 40, 500: 35},

                # Chemical Engineering (CHE)
                "CHEGEN": {100: 110, 200: 95, 300: 80, 400: 70, 500: 60},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Engineering Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

