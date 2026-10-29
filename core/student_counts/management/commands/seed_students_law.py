"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Law (LAW) at NSUK (5-year curriculum).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Law (LAW) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Law (LAW) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="LAW").first()
            if not faculty:
                self.stderr.write("Faculty LAW not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            # 5-year LL.B Programs (100L - 500L)
            populations = {
                # Public and International Law (PIL)
                "PILGEN": {100: 180, 200: 160, 300: 140, 400: 125, 500: 110},
                "PILISL": {100: 70, 200: 60, 300: 50, 400: 45, 500: 40},

                # Private and Commercial Law (PCL)
                "PCLGEN": {100: 170, 200: 150, 300: 135, 400: 120, 500: 105},
                "PCLTRD": {100: 65, 200: 55, 300: 45, 400: 40, 500: 35},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Law Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

