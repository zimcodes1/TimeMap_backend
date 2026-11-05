"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Medical and Health Sciences (FMHS) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Medical and Health Sciences (FMHS) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Medical and Health Sciences (FMHS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FMHS").first()
            if not faculty:
                self.stderr.write("Faculty FMHS not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            populations = {
                # Medicine and Surgery (MED) - 6-year MBBS curriculum
                "MEDGEN": {100: 150, 200: 130, 300: 110, 400: 95, 500: 85, 600: 75},

                # Nursing Science (NUR) - 5-year BNSc curriculum
                "NURGEN": {100: 160, 200: 135, 300: 115, 400: 100, 500: 85},

                # Medical Laboratory Science (MLS) - 5-year B.MLS curriculum
                "MLSGEN": {100: 130, 200: 110, 300: 95, 400: 80, 500: 70},

                # Public Health (PBH) - 4-year B.Sc curriculum
                "PBHGEN": {100: 120, 200: 100, 300: 80, 400: 65},
                "PBHCOM": {100: 75, 200: 60, 300: 50, 400: 40},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Medical & Health Sciences Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

