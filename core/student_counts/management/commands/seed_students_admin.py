"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Administration (ADMIN) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Administration (ADMIN) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Administration (ADMIN) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ADMIN").first()
            if not faculty:
                self.stderr.write("Faculty ADMIN not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            # Program codes and headcounts across 100L-400L
            populations = {
                # Business Administration (BAM)
                "BAMGEN": {100: 220, 200: 190, 300: 160, 400: 140},
                "BAMMKT": {100: 110, 200: 95, 300: 80, 400: 70},

                # Accounting (ACC)
                "ACCGEN": {100: 240, 200: 210, 300: 180, 400: 150},
                "ACCTAX": {100: 90, 200: 75, 300: 65, 400: 55},

                # Public Administration (PAD)
                "PADGEN": {100: 190, 200: 160, 300: 135, 400: 120},
                "PADLGA": {100: 85, 200: 70, 300: 60, 400: 50},

                # Banking and Finance (BFN)
                "BFNGEN": {100: 180, 200: 150, 300: 130, 400: 110},
                "BFNINS": {100: 80, 200: 65, 300: 55, 400: 45},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Administration Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

