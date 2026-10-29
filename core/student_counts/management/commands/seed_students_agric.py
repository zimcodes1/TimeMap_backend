"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Agriculture (AGRIC) at NSUK (5-year curriculum).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Agriculture (AGRIC) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Agriculture (AGRIC) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="AGRIC").first()
            if not faculty:
                self.stderr.write("Faculty AGRIC not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            # 5-year B.Agric / B.Sc Programs (100L - 500L)
            populations = {
                # Agronomy (AGR)
                "AGRGEN": {100: 110, 200: 90, 300: 75, 400: 65, 500: 55},
                "AGRSOIL": {100: 60, 200: 50, 300: 40, 400: 35, 500: 30},

                # Animal Science (ANS)
                "ANSGEN": {100: 105, 200: 85, 300: 70, 400: 60, 500: 50},
                "ANSPAS": {100: 50, 200: 40, 300: 35, 400: 30, 500: 25},

                # Agricultural Economics and Extension (AEE)
                "AEEGEN": {100: 120, 200: 100, 300: 85, 400: 70, 500: 60},
                "AEEEXT": {100: 75, 200: 60, 300: 50, 400: 45, 500: 35},

                # Fisheries and Aquaculture (FAQ)
                "FAQGEN": {100: 80, 200: 65, 300: 55, 400: 45, 500: 40},

                # Forestry and Wildlife Management (FOR)
                "FORGEN": {100: 70, 200: 55, 300: 45, 400: 40, 500: 30},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Agriculture Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

