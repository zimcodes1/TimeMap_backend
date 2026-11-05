"""
Management command to seed and complete lecturer assignments for the Faculty of Natural
and Applied Sciences (FNAS) and University General Studies (GST) courses at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed remaining lecturers and course assignments for FNAS and GST courses."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding FNAS Remaining Lecturers & Assignments ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FNAS").first()
            if not faculty:
                self.stderr.write("Faculty FNAS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            cmp_dept = depts.get("CMP")
            phy_dept = depts.get("PHY")
            chm_dept = depts.get("CHM")
            zoo_dept = depts.get("ZOO")

            # 1. Ensure Cyber & Software Lecturers in CMP
            extra_cmp_lecturers = [
                ("STAFF_CMP09", "Dr. Terver Ukeyima", "terver.ukeyima@nsuk.edu.ng", cmp_dept),
                ("STAFF_CMP10", "Engr. Fatima Danladi", "fatima.danladi@nsuk.edu.ng", cmp_dept),
                ("STAFF_CMP11", "Mr. Nnamdi Eze", "nnamdi.eze@nsuk.edu.ng", cmp_dept),
            ]
            for staff_id, name, email, d in extra_cmp_lecturers:
                if d:
                    ensure_lecturer(staff_id, name, email, d, default_password=password)

            # 2. Ensure Electronics Lecturers in PHY
            extra_phy_lecturers = [
                ("STAFF_PHY09", "Dr. Stephen Yakubu", "stephen.yakubu@nsuk.edu.ng", phy_dept),
                ("STAFF_PHY10", "Engr. Aisha Suleiman", "aisha.suleiman@nsuk.edu.ng", phy_dept),
            ]
            for staff_id, name, email, d in extra_phy_lecturers:
                if d:
                    ensure_lecturer(staff_id, name, email, d, default_password=password)

            # 3. Ensure Industrial Chemistry Lecturers in CHM
            extra_chm_lecturers = [
                ("STAFF_CHM09", "Dr. Oche Godwin", "oche.godwin@nsuk.edu.ng", chm_dept),
                ("STAFF_CHM10", "Dr. Halima Abdullahi", "halima.abdullahi@nsuk.edu.ng", chm_dept),
            ]
            for staff_id, name, email, d in extra_chm_lecturers:
                if d:
                    ensure_lecturer(staff_id, name, email, d, default_password=password)

            # Assign to unassigned FNAS courses
            cmp_lecs = list(LecturerStaff.objects.filter(department=cmp_dept))
            phy_lecs = list(LecturerStaff.objects.filter(department=phy_dept))
            chm_lecs = list(LecturerStaff.objects.filter(department=chm_dept))
            zoo_lecs = list(LecturerStaff.objects.filter(department=zoo_dept))

            course_map = {
                # CMP
                "CYS201": cmp_lecs[-2:],
                "CYS301": cmp_lecs[-3:-1],
                "CYS401": cmp_lecs[-1:],
                "SWE401": cmp_lecs[-2:],
                # PHY
                "ELX201": phy_lecs[-2:],
                "ELX301": phy_lecs[-1:],
                "ELX401": phy_lecs[-2:],
                # CHM
                "ICH201": chm_lecs[-2:],
                "ICH301": chm_lecs[-1:],
                "ICH401": chm_lecs[-2:],
                # ZOO
                "BIO107": zoo_lecs[:2],
            }

            assigned_count = 0
            for code, lecs in course_map.items():
                c = Course.objects.filter(owning_school=school, code=code).first()
                if c and lecs:
                    assign_lecturers_to_course(c, lecs)
                    assigned_count += 1

            # 4. GST Courses
            gst_prs = LecturerStaff.objects.filter(department__code="PRS").first()
            gst_pol = LecturerStaff.objects.filter(department__code="POL").first()
            gst_bam = LecturerStaff.objects.filter(department__code="BAM").first()

            if gst_prs:
                c211 = Course.objects.filter(owning_school=school, code="GST211").first()
                if c211:
                    assign_lecturers_to_course(c211, [gst_prs])
            if gst_pol:
                c221 = Course.objects.filter(owning_school=school, code="GST221").first()
                if c221:
                    assign_lecturers_to_course(c221, [gst_pol])
            if gst_bam:
                c311 = Course.objects.filter(owning_school=school, code="GST311").first()
                if c311:
                    assign_lecturers_to_course(c311, [gst_bam])

            self.stdout.write(self.style.SUCCESS("=== FNAS Lecturer Assignments Completed! ==="))
            self.stdout.write(f"Assigned lecturers to {assigned_count} previously unassigned FNAS courses.")

