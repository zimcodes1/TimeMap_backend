"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Education (EDU) and its departments (EDF, STM, ASE, GAC) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Education (EDU)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Education (EDU) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="EDU").first()
            if not faculty:
                self.stderr.write("Faculty EDU not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            edf_dept = depts.get("EDF")
            stm_dept = depts.get("STM")
            ase_dept = depts.get("ASE")
            gac_dept = depts.get("GAC")

            lecturers_data = {
                # Educational Foundations (EDF)
                "EDF": [
                    ("STAFF_EDF01", "Prof. Alice E. Asun", "alice.asun@nsuk.edu.ng"),
                    ("STAFF_EDF02", "Dr. Jonathan M. Mba", "jonathan.mba@nsuk.edu.ng"),
                    ("STAFF_EDF03", "Dr. Hauwa K. Mainoma", "hauwa.mainoma@nsuk.edu.ng"),
                    ("STAFF_EDF04", "Mr. Peter S. Gyang", "peter.gyang@nsuk.edu.ng"),
                    ("STAFF_EDF05", "Mrs. Lami D. Gana", "lami.gana@nsuk.edu.ng"),
                    ("STAFF_EDF06", "Dr. Musa A. Ango", "musa.ango@nsuk.edu.ng"),
                ],
                # Science, Technology and Mathematics Education (STM)
                "STM": [
                    ("STAFF_STM01", "Prof. Joel O. Eriba", "joel.eriba@nsuk.edu.ng"),
                    ("STAFF_STM02", "Dr. Florence O. Agbo", "florence.agbo@nsuk.edu.ng"),
                    ("STAFF_STM03", "Dr. Ibrahim S. Bako", "ibrahim.bako.stm@nsuk.edu.ng"),
                    ("STAFF_STM04", "Mr. Chinedu P. Okeke", "chinedu.okeke.stm@nsuk.edu.ng"),
                    ("STAFF_STM05", "Mrs. Grace N. Danjuma", "grace.danjuma.stm@nsuk.edu.ng"),
                ],
                # Arts and Social Science Education (ASE)
                "ASE": [
                    ("STAFF_ASE01", "Prof. Stephen A. Odey", "stephen.odey@nsuk.edu.ng"),
                    ("STAFF_ASE02", "Dr. Laraba D. Keffi", "laraba.keffi.ase@nsuk.edu.ng"),
                    ("STAFF_ASE03", "Dr. Benjamin O. Ameh", "benjamin.ameh@nsuk.edu.ng"),
                    ("STAFF_ASE04", "Mr. Usman G. Sule", "usman.sule@nsuk.edu.ng"),
                    ("STAFF_ASE05", "Mrs. Veronica T. Dogo", "veronica.dogo@nsuk.edu.ng"),
                ],
                # Guidance and Counselling (GAC)
                "GAC": [
                    ("STAFF_GAC01", "Prof. Bulus I. Danladi", "bulus.danladi@nsuk.edu.ng"),
                    ("STAFF_GAC02", "Dr. Agnes N. Okoye", "agnes.okoye@nsuk.edu.ng"),
                    ("STAFF_GAC03", "Dr. Mohammed A. Lafia", "mohammed.lafia.gac@nsuk.edu.ng"),
                    ("STAFF_GAC04", "Mr. Timothy O. Idoko", "timothy.idoko@nsuk.edu.ng"),
                    ("STAFF_GAC05", "Mrs. Comfort K. Bako", "comfort.bako@nsuk.edu.ng"),
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

            self.stdout.write(self.style.SUCCESS("=== Faculty of Education Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

