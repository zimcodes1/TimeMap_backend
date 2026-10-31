"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Law (LAW) and its departments (PIL, PCL) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Law (LAW)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Law (LAW) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="LAW").first()
            if not faculty:
                self.stderr.write("Faculty LAW not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            pil_dept = depts.get("PIL")
            pcl_dept = depts.get("PCL")

            lecturers_data = {
                # Public and International Law (PIL)
                "PIL": [
                    ("STAFF_PIL01", "Prof. Maxwell M. Gidado (SAN)", "maxwell.gidado@nsuk.edu.ng"),
                    ("STAFF_PIL02", "Dr. Usman D. Keffi", "usman.keffi.law@nsuk.edu.ng"),
                    ("STAFF_PIL03", "Dr. Fatima A. Waziri-Azi", "fatima.waziri@nsuk.edu.ng"),
                    ("STAFF_PIL04", "Barr. Yakubu M. Senchi", "yakubu.senchi@nsuk.edu.ng"),
                    ("STAFF_PIL05", "Mrs. Angela O. Chukwuma", "angela.chukwuma@nsuk.edu.ng"),
                    ("STAFF_PIL06", "Dr. Al-Hassan M. Shuaib", "alhassan.shuaib@nsuk.edu.ng"),
                ],
                # Private and Commercial Law (PCL)
                "PCL": [
                    ("STAFF_PCL01", "Prof. Oluwole K. Agbede", "oluwole.agbede@nsuk.edu.ng"),
                    ("STAFF_PCL02", "Dr. Anthony C. Okpara", "anthony.okpara@nsuk.edu.ng"),
                    ("STAFF_PCL03", "Dr. Halima A. Mohammed", "halima.mohammed.law@nsuk.edu.ng"),
                    ("STAFF_PCL04", "Barr. Solomon N. Tsakpa", "solomon.tsakpa@nsuk.edu.ng"),
                    ("STAFF_PCL05", "Mrs. Grace D. Madaki", "grace.madaki@nsuk.edu.ng"),
                    ("STAFF_PCL06", "Dr. Chinedu S. Eke", "chinedu.eke@nsuk.edu.ng"),
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

            self.stdout.write(self.style.SUCCESS("=== Faculty of Law Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

