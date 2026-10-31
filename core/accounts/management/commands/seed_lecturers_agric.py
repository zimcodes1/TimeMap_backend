"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Agriculture (AGRIC) and its departments (AGR, ANS, AEE, FAQ, FOR) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Agriculture (AGRIC)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Agriculture (AGRIC) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="AGRIC").first()
            if not faculty:
                self.stderr.write("Faculty AGRIC not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            agr_dept = depts.get("AGR")
            ans_dept = depts.get("ANS")
            aee_dept = depts.get("AEE")
            faq_dept = depts.get("FAQ")
            for_dept = depts.get("FOR")

            lecturers_data = {
                # Agronomy (AGR)
                "AGR": [
                    ("STAFF_AGR01", "Prof. Haruna K. Ayuba", "haruna.ayuba.agr@nsuk.edu.ng"),
                    ("STAFF_AGR02", "Dr. Salihu A. Lukman", "salihu.lukman@nsuk.edu.ng"),
                    ("STAFF_AGR03", "Dr. Veronica S. Kalu", "veronica.kalu@nsuk.edu.ng"),
                    ("STAFF_AGR04", "Mr. Bitrus D. Yohanna", "bitrus.yohanna@nsuk.edu.ng"),
                    ("STAFF_AGR05", "Mrs. Amina U. Bello", "amina.bello.agr@nsuk.edu.ng"),
                    ("STAFF_AGR06", "Dr. Emmanuel O. Oche", "emmanuel.oche@nsuk.edu.ng"),
                ],
                # Animal Science (ANS)
                "ANS": [
                    ("STAFF_ANS01", "Prof. Augustine A. Ogah", "augustine.ogah@nsuk.edu.ng"),
                    ("STAFF_ANS02", "Dr. Dauda M. Ogara", "dauda.ogara@nsuk.edu.ng"),
                    ("STAFF_ANS03", "Dr. Felicia N. Ike", "felicia.ike@nsuk.edu.ng"),
                    ("STAFF_ANS04", "Mr. Mohammed S. Lafia", "mohammed.lafia@nsuk.edu.ng"),
                    ("STAFF_ANS05", "Mrs. Comfort A. John", "comfort.john@nsuk.edu.ng"),
                    ("STAFF_ANS06", "Dr. Sunday O. Adedokun", "sunday.adedokun@nsuk.edu.ng"),
                ],
                # Agricultural Economics and Extension (AEE)
                "AEE": [
                    ("STAFF_AEE01", "Prof. Jude A. Mbanasor", "jude.mbanasor@nsuk.edu.ng"),
                    ("STAFF_AEE02", "Dr. Keffi B. Danwanka", "keffi.danwanka@nsuk.edu.ng"),
                    ("STAFF_AEE03", "Dr. Aisha M. Aliyu", "aisha.aliyu.aee@nsuk.edu.ng"),
                    ("STAFF_AEE04", "Mr. Stephen O. Oga", "stephen.oga@nsuk.edu.ng"),
                    ("STAFF_AEE05", "Mrs. Rebecca T. Tsado", "rebecca.tsado@nsuk.edu.ng"),
                    ("STAFF_AEE06", "Dr. Peter G. Gidado", "peter.gidado@nsuk.edu.ng"),
                ],
                # Fisheries and Aquaculture (FAQ)
                "FAQ": [
                    ("STAFF_FAQ01", "Prof. Balarabe M. Shitu", "balarabe.shitu@nsuk.edu.ng"),
                    ("STAFF_FAQ02", "Dr. Mary O. Agbebi", "mary.agbebi@nsuk.edu.ng"),
                    ("STAFF_FAQ03", "Dr. Victor U. Eyo", "victor.eyo@nsuk.edu.ng"),
                    ("STAFF_FAQ04", "Mr. Ibrahim T. Jibril", "ibrahim.jibril@nsuk.edu.ng"),
                    ("STAFF_FAQ05", "Mrs. Deborah E. Pam", "deborah.pam.faq@nsuk.edu.ng"),
                ],
                # Forestry and Wildlife Management (FOR)
                "FOR": [
                    ("STAFF_FOR01", "Prof. Samuel A. Oluwalana", "samuel.oluwalana@nsuk.edu.ng"),
                    ("STAFF_FOR02", "Dr. Yakubu G. Keffi", "yakubu.keffi.for@nsuk.edu.ng"),
                    ("STAFF_FOR03", "Dr. Ngozi A. Nnaji", "ngozi.nnaji@nsuk.edu.ng"),
                    ("STAFF_FOR04", "Mr. Danjuma K. Bako", "danjuma.bako@nsuk.edu.ng"),
                    ("STAFF_FOR05", "Mrs. Zainab S. Garkuwa", "zainab.garkuwa@nsuk.edu.ng"),
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

            self.stdout.write(self.style.SUCCESS("=== Faculty of Agriculture Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

