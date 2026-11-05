"""
Management command to seed courses and access grants for the Faculty of Law (LAW)
at NSUK for the current active semester.

Departments (5-year curriculum: 100L - 500L):
- Public and International Law (PIL) -> Programs: PILGEN, PILISL (Common and Islamic Law)
- Private and Commercial Law (PCL) -> Programs: PCLGEN, PCLTRD (International Trade Law)

Level limits: 100L <= 10, 200L <= 8, 300L <= 7, 400L <= 6, 500L <= 6.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course
from courses.seeding_utils import (
    ensure_course,
    ensure_general_studies_courses,
    get_active_semester,
    grant_course_access,
    resolve_scope_admins,
)
from hierarchy.models import Department, Faculty, Program, School


class Command(BaseCommand):
    help = "Seed courses and access grants for Faculty of Law (LAW) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Law (LAW) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="LAW").first()
            if not faculty:
                self.stderr.write("Faculty LAW not found!")
                return

            active_semester = get_active_semester(school)
            if not active_semester:
                self.stderr.write("No active semester found! Please activate a semester first.")
                return

            school_admin, fac_admin, dept_admins = resolve_scope_admins(school, faculty)
            default_initiator = fac_admin or school_admin

            # 1. GST Courses
            gst_courses = ensure_general_studies_courses(school, active_semester, default_initiator)

            depts = {d.code: d for d in faculty.departments.all()}
            created_count = 0
            grant_count = 0

            pil_dept = depts.get("PIL")
            pcl_dept = depts.get("PCL")

            # 2. Core Law Courses (Curriculum 100L - 500L)
            law_courses_def = [
                # 100 Level
                ("LAW101", "Nigerian Legal System I", 100, "PIL", 2, Course.ExamType.CBT, 60),
                ("LAW103", "Legal Methods I", 100, "PCL", 2, Course.ExamType.CBT, 60),

                # 200 Level
                ("LAW201", "Constitutional Law I", 200, "PIL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW203", "Law of Contract I", 200, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW205", "Nigerian Legal System II", 200, "PIL", 2, Course.ExamType.WRITTEN, 120),

                # 300 Level
                ("LAW301", "Criminal Law I", 300, "PIL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW303", "Law of Torts I", 300, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW305", "Commercial Law I (Sale of Goods & Agency)", 300, "PCL", 2, Course.ExamType.WRITTEN, 120),

                # 400 Level
                ("LAW401", "Land Law I", 400, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW403", "Equity and Trusts I", 400, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW405", "Law of Evidence I", 400, "PIL", 2, Course.ExamType.WRITTEN, 120),
                ("PIL401", "Public International Law I", 400, "PIL", 2, Course.ExamType.WRITTEN, 120),

                # 500 Level
                ("LAW501", "Jurisprudence and Legal Theory I", 500, "PIL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW503", "Company Law and Partnership I", 500, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW505", "Family Law I", 500, "PCL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW507", "Oil and Gas Law I", 500, "PIL", 2, Course.ExamType.WRITTEN, 120),
                ("LAW599", "Long Essay / Legal Research Project", 500, "PIL", 1, Course.ExamType.WRITTEN, 120),
            ]

            for code, title, lvl, dept_code, occ, exam_t, dur in law_courses_def:
                d = depts.get(dept_code)
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=d, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                if is_new: created_count += 1

            # 3. Program-Specific Specializations
            # Common and Islamic Law (PILISL) under PIL
            if pil_dept:
                isl_prog = pil_dept.programs.filter(code="PILISL").first()
                if isl_prog:
                    for code, title, lvl in [
                        ("ISL101", "Islamic Jurisprudence (Usul al-Fiqh) I", 100),
                        ("ISL201", "Islamic Law of Transactions (Mu'amalat)", 200),
                        ("ISL301", "Islamic Family Law (Ahwal al-Shakhsiyyah)", 300),
                        ("ISL401", "Islamic Law of Succession (Mawarith & Wasaya)", 400),
                        ("ISL501", "Islamic Criminal Law (Hudud & Qisas)", 500),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, pil_dept, faculty, school, active_semester, target_program=isl_prog)
                        if is_new: created_count += 1

            # International Trade Law (PCLTRD) under PCL
            if pcl_dept:
                trd_prog = pcl_dept.programs.filter(code="PCLTRD").first()
                if trd_prog:
                    for code, title, lvl in [
                        ("TRD301", "International Trade Law and Institutions I", 300),
                        ("TRD401", "Law of Banking and Negotiable Instruments", 400),
                        ("TRD501", "International Commercial Arbitration", 500),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, pcl_dept, faculty, school, active_semester, target_program=trd_prog)
                        if is_new: created_count += 1

            # 4. Sharing between PIL and PCL (Both departments share core law courses across 100L-500L)
            shared_between_pil_pcl = [
                "LAW101", "LAW103", "LAW201", "LAW203", "LAW205",
                "LAW301", "LAW303", "LAW305", "LAW401", "LAW403",
                "LAW405", "PIL401", "LAW501", "LAW503", "LAW505", "LAW507"
            ]
            for c_code in shared_between_pil_pcl:
                c = Course.objects.filter(code=c_code).first()
                if not c: continue
                # If owned by PIL, grant to PCL; if owned by PCL, grant to PIL
                target_dept = pcl_dept if c.owning_department_id == pil_dept.id else pil_dept
                owner_admin = dept_admins.get(c.owning_department.code) if c.owning_department else default_initiator
                t_admin = dept_admins.get(target_dept.code) or default_initiator
                _, g_created = grant_course_access(c, target_dept, initiated_by=owner_admin, decided_by=t_admin)
                if g_created: grant_count += 1

            # 5. Grants: GST to both PIL & PCL
            for d in [pil_dept, pcl_dept]:
                if not d: continue
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115", "GST211", "GST221", "GST311"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 6. External Grants: Social Science & Arts Foundations for Law Students
            # POL101, SOC101, ELS101
            for ext_code in ["POL101", "SOC101", "ELS101"]:
                ext_c = Course.objects.filter(code=ext_code).first()
                if ext_c:
                    for d in [pil_dept, pcl_dept]:
                        if d:
                            d_admin = dept_admins.get(d.code) or default_initiator
                            _, g_created = grant_course_access(ext_c, d, initiated_by=default_initiator, decided_by=d_admin)
                            if g_created: grant_count += 1

        self.stdout.write(self.style.SUCCESS("=== Faculty of Law Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

