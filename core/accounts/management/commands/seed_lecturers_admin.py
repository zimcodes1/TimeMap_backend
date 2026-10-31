"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Administration (ADMIN) and its departments (BAM, ACC, BFN, PAD) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Administration (ADMIN)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Administration (ADMIN) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ADMIN").first()
            if not faculty:
                self.stderr.write("Faculty ADMIN not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            bam_dept = depts.get("BAM")
            acc_dept = depts.get("ACC")
            bfn_dept = depts.get("BFN")
            pad_dept = depts.get("PAD")

            lecturers_data = {
                # Business Administration (BAM)
                "BAM": [
                    ("STAFF_BAM01", "Prof. Usman A. Mohammed", "usman.mohammed@nsuk.edu.ng"),
                    ("STAFF_BAM02", "Dr. Aisha Garba Umar", "aisha.garba@nsuk.edu.ng"),
                    ("STAFF_BAM03", "Dr. Solomon O. Adeleke", "solomon.adeleke@nsuk.edu.ng"),
                    ("STAFF_BAM04", "Mrs. Maryam Kabir", "maryam.kabir@nsuk.edu.ng"),
                    ("STAFF_BAM05", "Mr. Emmanuel Chukwu", "emmanuel.chukwu@nsuk.edu.ng"),
                    ("STAFF_BAM06", "Dr. Hauwa Al-Mustapha", "hauwa.mustapha@nsuk.edu.ng"),
                ],
                # Accounting (ACC)
                "ACC": [
                    ("STAFF_ACC01", "Prof. Ibrahim S. Ahmed", "ibrahim.ahmed@nsuk.edu.ng"),
                    ("STAFF_ACC02", "Dr. (Mrs) Ngozi Okonjo-Nwosu", "ngozi.okonjo@nsuk.edu.ng"),
                    ("STAFF_ACC03", "Dr. Musa Tanko", "musa.tanko@nsuk.edu.ng"),
                    ("STAFF_ACC04", "Mr. Babatunde Gbadamosi", "babatunde.gbadamosi@nsuk.edu.ng"),
                    ("STAFF_ACC05", "Mrs. Zainab Bello", "zainab.bello@nsuk.edu.ng"),
                    ("STAFF_ACC06", "Dr. Kenneth Akpan", "kenneth.akpan@nsuk.edu.ng"),
                ],
                # Banking and Finance (BFN)
                "BFN": [
                    ("STAFF_BFN01", "Prof. Abdullahi D. Shehu", "abdullahi.shehu@nsuk.edu.ng"),
                    ("STAFF_BFN02", "Dr. Clementina N. Agbo", "clementina.agbo@nsuk.edu.ng"),
                    ("STAFF_BFN03", "Dr. Samuel O. Fakorede", "samuel.fakorede@nsuk.edu.ng"),
                    ("STAFF_BFN04", "Mrs. Fatima Yahaya", "fatima.yahaya@nsuk.edu.ng"),
                    ("STAFF_BFN05", "Mr. Chinedu Eze", "chinedu.eze@nsuk.edu.ng"),
                    ("STAFF_BFN06", "Dr. Halilu Haruna", "halilu.haruna@nsuk.edu.ng"),
                ],
                # Public Administration (PAD)
                "PAD": [
                    ("STAFF_PAD01", "Prof. Haruna K. Ayuba", "haruna.ayuba@nsuk.edu.ng"),
                    ("STAFF_PAD02", "Dr. Veronica D. Audu", "veronica.audu@nsuk.edu.ng"),
                    ("STAFF_PAD03", "Dr. Mohammed B. Sani", "mohammed.sani@nsuk.edu.ng"),
                    ("STAFF_PAD04", "Mr. Yusuf G. Aliyu", "yusuf.aliyu@nsuk.edu.ng"),
                    ("STAFF_PAD05", "Mrs. Deborah Pam", "deborah.pam@nsuk.edu.ng"),
                    ("STAFF_PAD06", "Dr. Timothy J. Ogwuche", "timothy.ogwuche@nsuk.edu.ng"),
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

                # Include any existing lecturers in DB (e.g. STAFF0004 in BAM)
                all_dept_lecs = list(LecturerStaff.objects.filter(department=dept_obj))
                seeded_lecturers[d_code] = all_dept_lecs

            # Course Assignment Mapping (distribute evenly)
            assigned_courses_count = 0
            for d_code, dept_obj in depts.items():
                dept_lecs = seeded_lecturers.get(d_code, [])
                if not dept_lecs:
                    continue

                courses = list(Course.objects.filter(owning_department=dept_obj).order_by("level", "code"))
                for idx, course in enumerate(courses):
                    lec1 = dept_lecs[idx % len(dept_lecs)]
                    assigned = [lec1]
                    # Assign co-lecturer for 100L / 200L or capstone courses
                    if course.level <= 200 or course.level >= 400:
                        lec2 = dept_lecs[(idx + 1) % len(dept_lecs)]
                        if lec2 != lec1:
                            assigned.append(lec2)

                    assign_lecturers_to_course(course, assigned)
                    assigned_courses_count += 1

            # Also assign faculty-owned courses ECO101 and ECO201 if present under ADMIN
            fac_courses = Course.objects.filter(owning_faculty=faculty, owning_department__isnull=True)
            admin_all_lecs = [l for lecs in seeded_lecturers.values() for l in lecs]
            for idx, c in enumerate(fac_courses):
                assign_lecturers_to_course(c, [admin_all_lecs[idx % len(admin_all_lecs)]])
                assigned_courses_count += 1

            # Assign GST311 (Entrepreneurship) to BAM lecturers
            gst311 = Course.objects.filter(owning_school=school, code="GST311").first()
            if gst311 and seeded_lecturers.get("BAM"):
                assign_lecturers_to_course(gst311, seeded_lecturers["BAM"][:2])

            self.stdout.write(self.style.SUCCESS("=== Faculty of Administration Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

