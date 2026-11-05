"""
Management command to seed realistic student planning populations (ProgramStudentCount)
for degree programs in the Faculty of Social Sciences (FSS) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from hierarchy.models import Faculty, Program, School
from student_counts.seeding_utils import seed_program_student_counts


class Command(BaseCommand):
    help = "Seed student populations for Faculty of Social Sciences (FSS) programs."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Student Populations for Faculty of Social Sciences (FSS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FSS").first()
            if not faculty:
                self.stderr.write("Faculty FSS not found!")
                return

            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            populations = {
                # Economics (ECO)
                "ECOGEN": {100: 220, 200: 185, 300: 155, 400: 130},
                "ECODEV": {100: 95, 200: 80, 300: 65, 400: 55},

                # Political Science (POL)
                "POLGEN": {100: 210, 200: 180, 300: 150, 400: 125},
                "POLINT": {100: 120, 200: 100, 300: 85, 400: 70},

                # Sociology (SOC)
                "SOCGEN": {100: 180, 200: 150, 300: 125, 400: 105},
                "SOCCRM": {100: 140, 200: 115, 300: 95, 400: 80},

                # Mass Communication (MAC)
                "MACGEN": {100: 230, 200: 195, 300: 165, 400: 140},
                "MACBRD": {100: 90, 200: 75, 300: 65, 400: 55},
                "MACADV": {100: 90, 200: 75, 300: 65, 400: 55},

                # Psychology (PSY)
                "PSYGEN": {100: 150, 200: 125, 300: 105, 400: 85},
            }

            records_count = 0
            for p_code, levels_dict in populations.items():
                prog = programs.get(p_code)
                if prog:
                    cnt = seed_program_student_counts(prog, levels_dict)
                    records_count += cnt
                else:
                    self.stderr.write(f"Warning: Program {p_code} not found!")

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Social Sciences Student Populations Complete! ==="))
            self.stdout.write(f"Updated {records_count} ProgramStudentCount records across {len(populations)} programs.")

