"""
Management command to seed courses and access grants for the Faculty of Administration (ADMIN)
at NSUK for the current active semester.

Departments:
- Business Administration (BAM) -> Programs: BAMGEN, BAMMKT (Marketing)
- Accounting (ACC) -> Programs: ACCGEN, ACCTAX (Taxation)
- Public Administration (PAD) -> Programs: PADGEN, PADLGA (Local Government Admin)
- Banking and Finance (BFN) -> Programs: BFNGEN, BFNINS (Insurance and Risk Management)

Level limits: 100L <= 10, 200L <= 8, 300L <= 7, 400L <= 6.
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
    help = "Seed courses and access grants for Faculty of Administration (ADMIN) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Administration (ADMIN) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ADMIN").first()
            if not faculty:
                self.stderr.write("Faculty ADMIN not found!")
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

            # 2. Departmental Courses
            admin_courses_def = [
                # Business Administration (BAM)
                ("BAM101", "Introduction to Business I", 100, "BAM", 2, Course.ExamType.CBT, 60),
                ("BAM201", "Principles of Management I", 200, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM203", "Business Law I", 200, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM301", "Organizational Behaviour I", 300, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM303", "Operations Research I", 300, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM305", "Human Resource Management I", 300, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM401", "Business Policy & Strategy I", 400, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM403", "Corporate Planning", 400, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM405", "International Business Management", 400, "BAM", 2, Course.ExamType.WRITTEN, 120),
                ("BAM499", "Research Project in Business Administration", 400, "BAM", 1, Course.ExamType.WRITTEN, 120),

                # Accounting (ACC)
                ("ACC101", "Principles of Accounting I", 100, "ACC", 2, Course.ExamType.CBT, 60),
                ("ACC201", "Financial Accounting I", 200, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC203", "Cost Accounting I", 200, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC301", "Management Accounting I", 300, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC303", "Auditing and Investigation I", 300, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC305", "Taxation Principles & Practice I", 300, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC401", "Advanced Financial Accounting I", 400, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC403", "Public Sector Accounting", 400, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC405", "International Accounting Standards", 400, "ACC", 2, Course.ExamType.WRITTEN, 120),
                ("ACC499", "Research Project in Accounting", 400, "ACC", 1, Course.ExamType.WRITTEN, 120),

                # Public Administration (PAD)
                ("PAD101", "Elements of Public Administration I", 100, "PAD", 2, Course.ExamType.CBT, 60),
                ("PAD201", "Administrative Theory I", 200, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD203", "Nigerian Public Administration I", 200, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD301", "Public Policy Analysis I", 300, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD303", "Comparative Public Administration", 300, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD305", "Public Financial Management", 300, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD401", "Development Administration I", 400, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD403", "Public Enterprises Management", 400, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD405", "Inter-Governmental Relations", 400, "PAD", 2, Course.ExamType.WRITTEN, 120),
                ("PAD499", "Research Project in Public Administration", 400, "PAD", 1, Course.ExamType.WRITTEN, 120),

                # Banking and Finance (BFN)
                ("BFN101", "Introduction to Finance I", 100, "BFN", 2, Course.ExamType.CBT, 60),
                ("BFN201", "Money and Banking I", 200, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN203", "Financial Systems and Markets I", 200, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN301", "Commercial Bank Management I", 300, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN303", "Corporate Finance I", 300, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN305", "Quantitative Analysis for Finance", 300, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN401", "Investment Analysis & Portfolio Management", 400, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN403", "International Finance I", 400, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN405", "Credit Management & Lending", 400, "BFN", 2, Course.ExamType.WRITTEN, 120),
                ("BFN499", "Research Project in Banking and Finance", 400, "BFN", 1, Course.ExamType.WRITTEN, 120),
            ]

            for code, title, lvl, dept_code, occ, exam_t, dur in admin_courses_def:
                d = depts.get(dept_code)
                c, is_new = ensure_course(
                    code=code,
                    title=title,
                    level=lvl,
                    department=d,
                    faculty=faculty,
                    school=school,
                    active_semester=active_semester,
                    occurrences=occ,
                    exam_type=exam_t,
                    exam_duration=dur,
                )
                if is_new: created_count += 1

            # 3. Program-Specific Specializations
            # Marketing (BAMMKT) under BAM
            bam_dept = depts.get("BAM")
            if bam_dept:
                mkt_prog = bam_dept.programs.filter(code="BAMMKT").first()
                if mkt_prog:
                    for code, title, lvl in [
                        ("MKT301", "Marketing Management I", 300),
                        ("MKT401", "Consumer Behaviour & Market Research", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, bam_dept, faculty, school, active_semester, target_program=mkt_prog)
                        if is_new: created_count += 1

            # Taxation (ACCTAX) under ACC
            acc_dept = depts.get("ACC")
            if acc_dept:
                tax_prog = acc_dept.programs.filter(code="ACCTAX").first()
                if tax_prog:
                    for code, title, lvl in [
                        ("TAX301", "Personal Income Taxation & Practice", 300),
                        ("TAX401", "Corporate Tax Audit and Investigation", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, acc_dept, faculty, school, active_semester, target_program=tax_prog)
                        if is_new: created_count += 1

            # Local Government (PADLGA) under PAD
            pad_dept = depts.get("PAD")
            if pad_dept:
                lga_prog = pad_dept.programs.filter(code="PADLGA").first()
                if lga_prog:
                    for code, title, lvl in [
                        ("LGA301", "Local Government Systems and Process", 300),
                        ("LGA401", "Rural Development & Community Governance", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, pad_dept, faculty, school, active_semester, target_program=lga_prog)
                        if is_new: created_count += 1

            # Insurance (BFNINS) under BFN
            bfn_dept = depts.get("BFN")
            if bfn_dept:
                ins_prog = bfn_dept.programs.filter(code="BFNINS").first()
                if ins_prog:
                    for code, title, lvl in [
                        ("INS301", "Principles and Practice of Insurance", 300),
                        ("INS401", "Underwriting and Claims Management", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, bfn_dept, faculty, school, active_semester, target_program=ins_prog)
                        if is_new: created_count += 1

            # 4. Grants: University GST Courses to all Admin Departments
            for d in depts.values():
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115", "GST211", "GST221", "GST311"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 5. Inter-Departmental Faculty-Wide Sharing within ADMIN
            faculty_sharing = [
                ("BAM101", ["ACC", "PAD", "BFN"]),
                ("ACC101", ["BAM", "PAD", "BFN"]),
                ("PAD101", ["BAM", "BFN"]),
                ("BFN101", ["BAM", "ACC"]),
                ("BAM201", ["ACC", "PAD", "BFN"]),
                ("BAM203", ["ACC", "BFN"]),
            ]
            for course_code, target_codes in faculty_sharing:
                c = Course.objects.filter(code=course_code).first()
                if not c: continue
                owner_admin = dept_admins.get(c.owning_department.code if c.owning_department else "") or default_initiator
                for t_code in target_codes:
                    t_dept = depts.get(t_code)
                    if t_dept and t_dept.id != c.owning_department_id:
                        t_admin = dept_admins.get(t_code) or default_initiator
                        _, g_created = grant_course_access(c, t_dept, initiated_by=owner_admin, decided_by=t_admin)
                        if g_created: grant_count += 1

            # 6. Inter-Faculty Sharing (from FSS & FNAS)
            # Economics (ECO101, ECO201) and Computing (COS101)
            external_grants = [
                ("ECO101", ["BAM", "ACC", "BFN", "PAD"]),
                ("ECO201", ["BFN", "BAM", "ACC"]),
                ("COS101", ["BAM", "ACC", "PAD", "BFN"]),
                ("STA101", ["BAM", "ACC", "BFN", "PAD"]),
            ]
            for ext_code, target_codes in external_grants:
                c = Course.objects.filter(code=ext_code).first()
                if not c:
                    # Ensure it if not created yet
                    if ext_code == "ECO101":
                        c, _ = ensure_course("ECO101", "Principles of Economics I (Micro)", 100, None, faculty, school, active_semester, exam_type=Course.ExamType.CBT)
                    elif ext_code == "ECO201":
                        c, _ = ensure_course("ECO201", "Macroeconomic Theory I", 200, None, faculty, school, active_semester, exam_type=Course.ExamType.WRITTEN)
                if c:
                    for t_code in target_codes:
                        t_dept = depts.get(t_code)
                        if t_dept:
                            t_admin = dept_admins.get(t_code) or default_initiator
                            _, g_created = grant_course_access(c, t_dept, initiated_by=default_initiator, decided_by=t_admin)
                            if g_created: grant_count += 1

        self.stdout.write(self.style.SUCCESS("=== Faculty of Administration Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

