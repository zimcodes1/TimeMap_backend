"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Arts (ARTS) and its departments (ELS, HIS, LIN, PRS, TMA) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Arts (ARTS)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Arts (ARTS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ARTS").first()
            if not faculty:
                self.stderr.write("Faculty ARTS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            els_dept = depts.get("ELS")
            his_dept = depts.get("HIS")
            lin_dept = depts.get("LIN")
            prs_dept = depts.get("PRS")
            tma_dept = depts.get("TMA")

            lecturers_data = {
                # English and Literary Studies (ELS)
                "ELS": [
                    ("STAFF_ELS01", "Prof. Oluwatoyin O. Jegede", "oluwatoyin.jegede@nsuk.edu.ng"),
                    ("STAFF_ELS02", "Dr. Terzungwe Atim", "terzungwe.atim@nsuk.edu.ng"),
                    ("STAFF_ELS03", "Dr. Comfort E. Anzaku", "comfort.anzaku@nsuk.edu.ng"),
                    ("STAFF_ELS04", "Mr. Balarabe Mohammed", "balarabe.mohammed@nsuk.edu.ng"),
                    ("STAFF_ELS05", "Mrs. Judith O. Okoro", "judith.okoro@nsuk.edu.ng"),
                    ("STAFF_ELS06", "Dr. Yusuf A. Danjuma", "yusuf.danjuma@nsuk.edu.ng"),
                ],
                # History and International Studies (HIS)
                "HIS": [
                    ("STAFF_HIS01", "Prof. Yakubu M. Ochefu", "yakubu.ochefu@nsuk.edu.ng"),
                    ("STAFF_HIS02", "Dr. Hadiza I. Kiari", "hadiza.kiari@nsuk.edu.ng"),
                    ("STAFF_HIS03", "Dr. George K. Akume", "george.akume@nsuk.edu.ng"),
                    ("STAFF_HIS04", "Mr. Abubakar S. Jibrin", "abubakar.jibrin@nsuk.edu.ng"),
                    ("STAFF_HIS05", "Mrs. Grace M. Dung", "grace.dung@nsuk.edu.ng"),
                    ("STAFF_HIS06", "Dr. Festus O. Osagie", "festus.osagie@nsuk.edu.ng"),
                ],
                # Languages and Linguistics (LIN)
                "LIN": [
                    ("STAFF_LIN01", "Prof. Mahmoud A. Al-Hassan", "mahmoud.alhassan@nsuk.edu.ng"),
                    ("STAFF_LIN02", "Dr. Claire B. Dubois-Garba", "claire.dubois@nsuk.edu.ng"),
                    ("STAFF_LIN03", "Dr. Samuel B. Gadu", "samuel.gadu@nsuk.edu.ng"),
                    ("STAFF_LIN04", "Mal. Ibrahim Khalil", "ibrahim.khalil@nsuk.edu.ng"),
                    ("STAFF_LIN05", "Mrs. Roseline N. Umeh", "roseline.umeh@nsuk.edu.ng"),
                    ("STAFF_LIN06", "Dr. Fatima T. Sanusi", "fatima.sanusi@nsuk.edu.ng"),
                ],
                # Philosophy and Religious Studies (PRS)
                "PRS": [
                    ("STAFF_PRS01", "Prof. Emmanuel C. Anagwo", "emmanuel.anagwo@nsuk.edu.ng"),
                    ("STAFF_PRS02", "Dr. Usman B. Lafia", "usman.lafia@nsuk.edu.ng"),
                    ("STAFF_PRS03", "Rev. Fr. Dr. Matthew Audu", "matthew.audu@nsuk.edu.ng"),
                    ("STAFF_PRS04", "Dr. Aisha M. Keffi", "aisha.keffi@nsuk.edu.ng"),
                    ("STAFF_PRS05", "Mr. Philip O. Omoni", "philip.omoni@nsuk.edu.ng"),
                    ("STAFF_PRS06", "Dr. Timothy S. Baba", "timothy.baba@nsuk.edu.ng"),
                ],
                # Theatre and Media Arts (TMA)
                "TMA": [
                    ("STAFF_TMA01", "Prof. Sunday E. Ododo", "sunday.ododo@nsuk.edu.ng"),
                    ("STAFF_TMA02", "Dr. Laraba P. Alfa", "laraba.alfa@nsuk.edu.ng"),
                    ("STAFF_TMA03", "Dr. Kenneth C. Nwafor", "kenneth.nwafor@nsuk.edu.ng"),
                    ("STAFF_TMA04", "Mr. Felix A. Idoko", "felix.idoko@nsuk.edu.ng"),
                    ("STAFF_TMA05", "Mrs. Christy K. Jerry", "christy.jerry@nsuk.edu.ng"),
                    ("STAFF_TMA06", "Dr. Musa A. Enna", "musa.enna@nsuk.edu.ng"),
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

            # Assign GST211 (Philosophy, Logic & Human Existence) to PRS lecturers
            gst211 = Course.objects.filter(owning_school=school, code="GST211").first()
            if gst211 and seeded_lecturers.get("PRS"):
                assign_lecturers_to_course(gst211, seeded_lecturers["PRS"][:2])

            self.stdout.write(self.style.SUCCESS("=== Faculty of Arts Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

