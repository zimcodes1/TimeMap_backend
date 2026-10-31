"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Medical and Health Sciences (FMHS) and its departments (MED, NUR, MLS, PBH) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Medical and Health Sciences (FMHS)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Medical & Health Sciences (FMHS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FMHS").first()
            if not faculty:
                self.stderr.write("Faculty FMHS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            med_dept = depts.get("MED")
            nur_dept = depts.get("NUR")
            mls_dept = depts.get("MLS")
            pbh_dept = depts.get("PBH")

            lecturers_data = {
                # Medicine and Surgery (MED)
                "MED": [
                    ("STAFF_MED01", "Prof. Stephen K. Obaro", "stephen.obaro@nsuk.edu.ng"),
                    ("STAFF_MED02", "Dr. Rosemary D. Audu (FWACS)", "rosemary.audu@nsuk.edu.ng"),
                    ("STAFF_MED03", "Dr. Victor M. Gana (FWACP)", "victor.gana.med@nsuk.edu.ng"),
                    ("STAFF_MED04", "Dr. Fatima A. Shuaibu", "fatima.shuaibu.med@nsuk.edu.ng"),
                    ("STAFF_MED05", "Dr. Kenneth O. Agbo", "kenneth.agbo.med@nsuk.edu.ng"),
                    ("STAFF_MED06", "Dr. Halima B. Sani", "halima.sani.med@nsuk.edu.ng"),
                    ("STAFF_MED07", "Dr. Emmanuel C. Chukwu", "emmanuel.chukwu.med@nsuk.edu.ng"),
                    ("STAFF_MED08", "Dr. Zainab M. Keffi", "zainab.keffi.med@nsuk.edu.ng"),
                ],
                # Nursing Science (NUR)
                "NUR": [
                    ("STAFF_NUR01", "Prof. Mildred E. John", "mildred.john@nsuk.edu.ng"),
                    ("STAFF_NUR02", "Dr. Comfort M. Anzaku", "comfort.anzaku.nur@nsuk.edu.ng"),
                    ("STAFF_NUR03", "Dr. Veronica T. Dogo", "veronica.dogo.nur@nsuk.edu.ng"),
                    ("STAFF_NUR04", "Mrs. Grace N. Danjuma", "grace.danjuma.nur@nsuk.edu.ng"),
                    ("STAFF_NUR05", "Mr. Timothy K. Bako", "timothy.bako.nur@nsuk.edu.ng"),
                    ("STAFF_NUR06", "Mrs. Angela O. Okoro", "angela.okoro.nur@nsuk.edu.ng"),
                ],
                # Medical Laboratory Science (MLS)
                "MLS": [
                    ("STAFF_MLS01", "Prof. Anthony A. Elujoba", "anthony.elujoba@nsuk.edu.ng"),
                    ("STAFF_MLS02", "Dr. Solomon O. Adeleke", "solomon.adeleke.mls@nsuk.edu.ng"),
                    ("STAFF_MLS03", "Dr. Hadiza I. Kiari", "hadiza.kiari.mls@nsuk.edu.ng"),
                    ("STAFF_MLS04", "Mr. Bitrus D. Yohanna", "bitrus.yohanna.mls@nsuk.edu.ng"),
                    ("STAFF_MLS05", "Mrs. Fatima T. Sanusi", "fatima.sanusi.mls@nsuk.edu.ng"),
                    ("STAFF_MLS06", "Dr. Peter G. Gidado", "peter.gidado.mls@nsuk.edu.ng"),
                ],
                # Public Health (PBH)
                "PBH": [
                    ("STAFF_PBH01", "Prof. Folashade B. Ogunsola", "folashade.ogunsola@nsuk.edu.ng"),
                    ("STAFF_PBH02", "Dr. Abubakar S. Jibrin", "abubakar.jibrin.pbh@nsuk.edu.ng"),
                    ("STAFF_PBH03", "Dr. Ngozi A. Nnaji", "ngozi.nnaji.pbh@nsuk.edu.ng"),
                    ("STAFF_PBH04", "Mr. Stephen O. Oga", "stephen.oga.pbh@nsuk.edu.ng"),
                    ("STAFF_PBH05", "Mrs. Deborah E. Pam", "deborah.pam.pbh@nsuk.edu.ng"),
                    ("STAFF_PBH06", "Dr. David A. Ayuba", "david.ayuba.pbh@nsuk.edu.ng"),
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
                    if course.level <= 200 or course.level >= 500:
                        lec2 = dept_lecs[(idx + 1) % len(dept_lecs)]
                        if lec2 != lec1:
                            assigned.append(lec2)

                    assign_lecturers_to_course(course, assigned)
                    assigned_courses_count += 1

            self.stdout.write(self.style.SUCCESS("=== Faculty of Medical & Health Sciences Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

