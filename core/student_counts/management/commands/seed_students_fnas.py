"""
Management command to seed and standardize realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Natural and Applied Sciences (FNAS) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Natural & Applied Sciences (FNAS) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Natural & Applied Sciences (FNAS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FNAS").first()
            if not faculty:
                self.stderr.write("Faculty FNAS not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            populations = {
                # Biochemistry (BCH)
                "BCHGEN": {100: 180, 200: 150, 300: 120, 400: 90},

                # Chemistry (CHM)
                "CHMGEN": {100: 140, 200: 110, 300: 85, 400: 60},
                "CHMPUR": {100: 140, 200: 110, 300: 85, 400: 60},
                "INDCHM": {100: 110, 200: 85, 300: 65, 400: 50},
                "CHMIND": {100: 110, 200: 85, 300: 65, 400: 50},

                # Computer Science (CMP)
                "CMPGEN": {100: 320, 200: 280, 300: 220, 400: 180},
                "CYB": {100: 120, 200: 100, 300: 80, 400: 65},
                "CMPCYS": {100: 120, 200: 100, 300: 80, 400: 65},
                "SWE": {100: 140, 200: 115, 300: 95, 400: 75},
                "CMPSWE": {100: 140, 200: 115, 300: 95, 400: 75},

                # Mathematics (MTH)
                "MTHGEN": {100: 130, 200: 100, 300: 80, 400: 60},

                # Microbiology (MCB)
                "MCBGEN": {100: 200, 200: 170, 300: 140, 400: 110},

                # Physics (PHY)
                "PHYGEN": {100: 110, 200: 85, 300: 65, 400: 45},
                "PHYELX": {100: 90, 200: 70, 300: 55, 400: 40},

                # Science Laboratory Technology (SLT)
                "SLTGEN": {100: 160, 200: 130, 300: 100, 400: 80},

                # Statistics (STA)
                "STAGEN": {100: 100, 200: 80, 300: 60, 400: 45},

                # Zoology (ZOO)
                "ZOOGEN": {100: 120, 200: 95, 300: 75, 400: 50},
            }

            records_count = 0
            matched_programs = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                    matched_programs += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Natural & Applied Sciences Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {matched_programs} programs.")

