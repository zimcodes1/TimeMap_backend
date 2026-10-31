"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Engineering (ENG) and its departments (CVE, EEE, MEE, CHE) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Engineering (ENG)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Engineering (ENG) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENG").first()
            if not faculty:
                self.stderr.write("Faculty ENG not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            cve_dept = depts.get("CVE")
            eee_dept = depts.get("EEE")
            mee_dept = depts.get("MEE")
            che_dept = depts.get("CHE")

            lecturers_data = {
                # Civil Engineering (CVE)
                "CVE": [
                    ("STAFF_CVE01", "Engr. Prof. Sadiq Z. Abubakar", "sadiq.abubakar@nsuk.edu.ng"),
                    ("STAFF_CVE02", "Engr. Dr. Patricia O. Nwankwo", "patricia.nwankwo@nsuk.edu.ng"),
                    ("STAFF_CVE03", "Engr. Dr. Bitrus M. Gana", "bitrus.gana.cve@nsuk.edu.ng"),
                    ("STAFF_CVE04", "Engr. Mr. Emmanuel K. Idoko", "emmanuel.idoko.cve@nsuk.edu.ng"),
                    ("STAFF_CVE05", "Engr. Mrs. Fatima U. Suleiman", "fatima.suleiman.cve@nsuk.edu.ng"),
                    ("STAFF_CVE06", "Engr. Dr. Kenneth A. Bako", "kenneth.bako.cve@nsuk.edu.ng"),
                ],
                # Electrical and Electronics Engineering (EEE)
                "EEE": [
                    ("STAFF_EEE01", "Engr. Prof. Ayodeji O. Salau", "ayodeji.salau@nsuk.edu.ng"),
                    ("STAFF_EEE02", "Engr. Dr. Halima S. Aliyu", "halima.aliyu.eee@nsuk.edu.ng"),
                    ("STAFF_EEE03", "Engr. Dr. Solomon C. Nnamdi", "solomon.nnamdi.eee@nsuk.edu.ng"),
                    ("STAFF_EEE04", "Engr. Mr. Danjuma K. Keffi", "danjuma.keffi.eee@nsuk.edu.ng"),
                    ("STAFF_EEE05", "Engr. Mrs. Angela O. Chukwu", "angela.chukwu.eee@nsuk.edu.ng"),
                    ("STAFF_EEE06", "Engr. Dr. Mohammed B. Lafia", "mohammed.lafia.eee@nsuk.edu.ng"),
                ],
                # Mechanical Engineering (MEE)
                "MEE": [
                    ("STAFF_MEE01", "Engr. Prof. Stephen A. Olurotimi", "stephen.olurotimi@nsuk.edu.ng"),
                    ("STAFF_MEE02", "Engr. Dr. Veronica M. Audu", "veronica.audu.mee@nsuk.edu.ng"),
                    ("STAFF_MEE03", "Engr. Dr. Ibrahim G. Jibrin", "ibrahim.jibrin.mee@nsuk.edu.ng"),
                    ("STAFF_MEE04", "Engr. Mr. Peter S. Gyang", "peter.gyang.mee@nsuk.edu.ng"),
                    ("STAFF_MEE05", "Engr. Mrs. Deborah E. Eze", "deborah.eze.mee@nsuk.edu.ng"),
                    ("STAFF_MEE06", "Engr. Dr. Timothy O. Bako", "timothy.bako.mee@nsuk.edu.ng"),
                ],
                # Chemical Engineering (CHE)
                "CHE": [
                    ("STAFF_CHE01", "Engr. Prof. Baba Y. Jibril", "baba.jibril@nsuk.edu.ng"),
                    ("STAFF_CHE02", "Engr. Dr. Rosemary N. Agbo", "rosemary.agbo.che@nsuk.edu.ng"),
                    ("STAFF_CHE03", "Engr. Dr. Victor O. Ameh", "victor.ameh.che@nsuk.edu.ng"),
                    ("STAFF_CHE04", "Engr. Mr. Abubakar S. Sani", "abubakar.sani.che@nsuk.edu.ng"),
                    ("STAFF_CHE05", "Engr. Mrs. Grace T. Danladi", "grace.danladi.che@nsuk.edu.ng"),
                    ("STAFF_CHE06", "Engr. Dr. Aliyu D. Haruna", "aliyu.haruna.che@nsuk.edu.ng"),
                ],
            }

            seeded_lecturers = {}
            total_lecturers_created = 0

            for d_code, lecs_list in lecturers_data.items():
                dept_obj = depts.get(d_code)
                seeded_lecturers[d_code] = []
                for s_id, name, email in lecs_list:
                    lec, created = ensure_lecturer(s_id, name, email, dept_obj, default_password=password)
                    seeded_lecturers[d_code].append(lec)
                    if created:
                        total_lecturers_created += 1

                all_dept_lecs = list(LecturerStaff.objects.filter(department=dept_obj))
                seeded_lecturers[d_code] = all_dept_lecs

            # Course Assignment Mapping
            assigned_courses_count = 0
            for d_code, dept_obj in depts.items():
                dept_lecs = seeded_lecturers.get(d_code, [])
                if not dept_lecs:
                    continue

                courses = list(Course.objects.filter(owning_department=dept_obj).order_by("level", "code"))
                for idx, course in enumerate(courses):
                    lec1 = dept_lecs[idx % len(dept_lecs)]
                    assigned = [lec1]
                    if course.level <= 200 or course.level >= 400:
                        lec2 = dept_lecs[(idx + 1) % len(dept_lecs)]
                        if lec2 != lec1:
                            assigned.append(lec2)

                    assign_lecturers_to_course(course, assigned)
                    assigned_courses_count += 1

            self.stdout.write(self.style.SUCCESS("=== Faculty of Engineering Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

