"""
Management command to seed courses and access grants for the Faculty of Agriculture (AGRIC)
at NSUK for the current active semester.

Departments (5-year curriculum: 100L - 500L):
- Agronomy (AGR) -> Programs: AGRGEN, AGRSOIL (Soil Science)
- Animal Science (ANS) -> Programs: ANSGEN, ANSPAS (Pasture & Range Mgt)
- Agricultural Economics and Extension (AEE) -> Programs: AEEGEN, AEEEXT (Agricultural Extension)
- Fisheries and Aquaculture (FAQ) -> Programs: FAQGEN
- Forestry and Wildlife Management (FOR) -> Programs: FORGEN

Level limits: 100L <= 10, 200L <= 8, 300L <= 7, 400L <= 6 (FPY), 500L <= 6.
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
    help = "Seed courses and access grants for Faculty of Agriculture (AGRIC) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Agriculture (AGRIC) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="AGRIC").first()
            if not faculty:
                self.stderr.write("Faculty AGRIC not found!")
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

            # 2. Agricultural Courses (100L, 200L, 300L, 400L FPY, 500L)
            agric_courses_def = [
                # 100L Common Faculty Intro
                ("AGR101", "Introduction to Agriculture I", 100, "AGR", 2, Course.ExamType.CBT, 60),

                # 200L Shared Core
                ("AGR201", "Principles of Crop Production I", 200, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("AGR203", "Introduction to Soil Science", 200, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("ANS201", "Introduction to Animal Science", 200, "ANS", 2, Course.ExamType.WRITTEN, 120),
                ("AEE201", "Principles of Agricultural Economics", 200, "AEE", 2, Course.ExamType.WRITTEN, 120),
                ("FAQ201", "Introduction to Fisheries and Aquaculture", 200, "FAQ", 2, Course.ExamType.WRITTEN, 120),
                ("FOR201", "Introduction to Forestry and Wildlife Management", 200, "FOR", 2, Course.ExamType.WRITTEN, 120),

                # 300L Departmental
                ("AGR301", "Arable Crop Production", 300, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("AGR303", "Weed Science and Management", 300, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("ANS301", "Ruminant Animal Production", 300, "ANS", 2, Course.ExamType.WRITTEN, 120),
                ("ANS303", "Non-Ruminant Production", 300, "ANS", 2, Course.ExamType.WRITTEN, 120),
                ("AEE301", "Farm Management and Accounting", 300, "AEE", 2, Course.ExamType.WRITTEN, 120),
                ("AEE303", "Agricultural Marketing and Cooperatives", 300, "AEE", 2, Course.ExamType.WRITTEN, 120),
                ("FAQ301", "Fish Ecology and Taxonomy", 300, "FAQ", 2, Course.ExamType.WRITTEN, 120),
                ("FAQ303", "Aquaculture Engineering & Water Quality", 300, "FAQ", 2, Course.ExamType.WRITTEN, 120),
                ("FOR301", "Dendrology and Forest Botany", 300, "FOR", 2, Course.ExamType.WRITTEN, 120),
                ("FOR303", "Wildlife Ecology and Conservation", 300, "FOR", 2, Course.ExamType.WRITTEN, 120),

                # 400L Farm Practical Year (FPY) Modules
                ("FPY401", "Crop Production & Horticultural Farm Practice", 400, "AGR", 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("FPY403", "Livestock Management & Poultry Farm Practice", 400, "ANS", 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("FPY405", "Agricultural Mechanization & Workshop Practice", 400, "AGR", 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("FPY407", "Fisheries & Wildlife Field Experience", 400, "FAQ", 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("FPY409", "Agro-Business & Rural Extension Practicum", 400, "AEE", 1, Course.ExamType.LAB_PRACTICAL, 120),

                # 500L Advanced Specializations
                ("AGR501", "Crop Breeding and Genetics", 500, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("AGR503", "Plant Pathology & Integrated Pest Management", 500, "AGR", 2, Course.ExamType.WRITTEN, 120),
                ("AGR599", "Research Project in Agronomy", 500, "AGR", 1, Course.ExamType.WRITTEN, 120),

                ("ANS501", "Animal Nutrition & Feed Formulation", 500, "ANS", 2, Course.ExamType.WRITTEN, 120),
                ("ANS503", "Animal Breeding and Genetics", 500, "ANS", 2, Course.ExamType.WRITTEN, 120),
                ("ANS599", "Research Project in Animal Science", 500, "ANS", 1, Course.ExamType.WRITTEN, 120),

                ("AEE501", "Agricultural Policy, Finance & Development", 500, "AEE", 2, Course.ExamType.WRITTEN, 120),
                ("AEE503", "Quantitative Methods & Econometrics for Agriculture", 500, "AEE", 2, Course.ExamType.WRITTEN, 120),
                ("AEE599", "Research Project in Agricultural Economics", 500, "AEE", 1, Course.ExamType.WRITTEN, 120),

                ("FAQ501", "Fish Nutrition and Feed Technology", 500, "FAQ", 2, Course.ExamType.WRITTEN, 120),
                ("FAQ503", "Fish Diseases, Parasitology & Health Mgt", 500, "FAQ", 2, Course.ExamType.WRITTEN, 120),
                ("FAQ599", "Research Project in Fisheries", 500, "FAQ", 1, Course.ExamType.WRITTEN, 120),

                ("FOR501", "Silviculture and Forest Management", 500, "FOR", 2, Course.ExamType.WRITTEN, 120),
                ("FOR503", "Forest Economics and Policy", 500, "FOR", 2, Course.ExamType.WRITTEN, 120),
                ("FOR599", "Research Project in Forestry", 500, "FOR", 1, Course.ExamType.WRITTEN, 120),
            ]

            for code, title, lvl, dept_code, occ, exam_t, dur in agric_courses_def:
                d = depts.get(dept_code)
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=d, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                if is_new: created_count += 1

            # 3. Program-Specific Specializations
            # Soil Science (AGRSOIL)
            agr_dept = depts.get("AGR")
            if agr_dept:
                soil_prog = agr_dept.programs.filter(code="AGRSOIL").first()
                if soil_prog:
                    for code, title, lvl in [
                        ("SOL301", "Soil Fertility and Plant Nutrition", 300),
                        ("SOL501", "Soil Microbiology & Biochemistry", 500),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, agr_dept, faculty, school, active_semester, target_program=soil_prog)
                        if is_new: created_count += 1

            # Pasture & Range Management (ANSPAS)
            ans_dept = depts.get("ANS")
            if ans_dept:
                pas_prog = ans_dept.programs.filter(code="ANSPAS").first()
                if pas_prog:
                    for code, title, lvl in [
                        ("PAS301", "Pasture and Forage Agronomy", 300),
                        ("PAS501", "Range Ecology and Grazing Management", 500),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, ans_dept, faculty, school, active_semester, target_program=pas_prog)
                        if is_new: created_count += 1

            # Agricultural Extension (AEEEXT)
            aee_dept = depts.get("AEE")
            if aee_dept:
                ext_prog = aee_dept.programs.filter(code="AEEEXT").first()
                if ext_prog:
                    for code, title, lvl in [
                        ("AEE305", "Extension Teaching and Communication Methods", 300),
                        ("AEE505", "Diffusion and Adoption of Innovations", 500),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, aee_dept, faculty, school, active_semester, target_program=ext_prog)
                        if is_new: created_count += 1

            # 4. Grants: GST to all Agric Departments
            for d in depts.values():
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115", "GST211", "GST221", "GST311"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 5. Sharing AGR101 and 200L Core Courses across all Agric Departments
            agric_core_codes = ["AGR101", "AGR201", "AGR203", "ANS201", "AEE201", "FAQ201", "FOR201"]
            for c_code in agric_core_codes:
                c = Course.objects.filter(code=c_code).first()
                if not c: continue
                owner_admin = dept_admins.get(c.owning_department.code if c.owning_department else "") or default_initiator
                for d in depts.values():
                    if d.id != c.owning_department_id:
                        d_admin = dept_admins.get(d.code) or default_initiator
                        _, g_created = grant_course_access(c, d, initiated_by=owner_admin, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 6. Farm Practical Year (FPY 400L) shared to all Agric departments
            fpy_codes = ["FPY401", "FPY403", "FPY405", "FPY407", "FPY409"]
            for c_code in fpy_codes:
                c = Course.objects.filter(code=c_code).first()
                if not c: continue
                owner_admin = dept_admins.get(c.owning_department.code if c.owning_department else "") or default_initiator
                for d in depts.values():
                    if d.id != c.owning_department_id:
                        d_admin = dept_admins.get(d.code) or default_initiator
                        _, g_created = grant_course_access(c, d, initiated_by=owner_admin, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 7. External Grants from FNAS (Sciences) & FSS (Economics)
            external_grants = [
                ("BIO101", ["AGR", "ANS", "FAQ", "FOR"]),
                ("BIO107", ["AGR", "ANS", "FAQ", "FOR"]),
                ("CHM101", ["AGR", "ANS", "FAQ", "FOR"]),
                ("CHM107", ["AGR", "ANS", "FAQ", "FOR"]),
                ("MTH101", ["AGR", "ANS", "AEE"]),
                ("PHY101", ["AGR", "AEE"]),
                ("STA101", ["AGR", "ANS", "AEE", "FAQ", "FOR"]),
                ("ECO101", ["AEE"]),
            ]
            for ext_code, target_codes in external_grants:
                c = Course.objects.filter(code=ext_code).first()
                if c:
                    for t_code in target_codes:
                        t_dept = depts.get(t_code)
                        if t_dept:
                            t_admin = dept_admins.get(t_code) or default_initiator
                            _, g_created = grant_course_access(c, t_dept, initiated_by=default_initiator, decided_by=t_admin)
                            if g_created: grant_count += 1

        self.stdout.write(self.style.SUCCESS("=== Faculty of Agriculture Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

