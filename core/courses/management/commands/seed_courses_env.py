"""
Management command to seed courses and access grants for the Faculty of Environmental Science (ENV)
at NSUK for the current active semester.

Departments:
- Architecture (ARC, 500L) -> ARCGEN
- Geography and Environmental Management (GEO, 400L) -> GEOENV, GEOGEN
- Urban and Regional Planning (URP, 500L) -> URPGEN
- Estate Management (ESM, 500L) -> ESMGEN
- Quantity Surveying (QTS, 500L) -> QTSGEN

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
    help = "Seed courses and access grants for Faculty of Environmental Science (ENV) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Environmental Science (ENV) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENV").first()
            if not faculty:
                self.stderr.write("Faculty ENV not found!")
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

            arc_dept = depts.get("ARC")
            geo_dept = depts.get("GEO")
            urp_dept = depts.get("URP")
            esm_dept = depts.get("ESM")
            qts_dept = depts.get("QTS")

            # 2. Shared Faculty Environmental Science Courses
            env_common_courses = [
                ("ENV101", "Introduction to Built Environment", 100, arc_dept, 2, Course.ExamType.CBT, 60),
                ("ENV103", "Basic Technical & Architectural Graphics I", 100, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENV201", "Principles of Land Surveying & Geoinformatics", 200, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENV203", "Building Construction Materials & Methods I", 200, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENV301", "Environmental Impact Assessment & Law", 300, geo_dept, 2, Course.ExamType.WRITTEN, 120),
            ]

            env_course_objs = {}
            for code, title, lvl, dept_ref, occ, exam_t, dur in env_common_courses:
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=dept_ref, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                env_course_objs[code] = c
                if is_new:
                    created_count += 1

            # 3. Department Specific Courses
            dept_courses = [
                # === Architecture (ARC) ===
                ("ARC201", "Architectural Design Studio I", 200, arc_dept, 2, Course.ExamType.WRITTEN, 180),
                ("ARC203", "History of Architecture I", 200, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC301", "Architectural Design Studio III", 300, arc_dept, 2, Course.ExamType.WRITTEN, 180),
                ("ARC303", "Building Structures I", 300, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC305", "Building Services & Environmental Science I", 300, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC307", "CAD & Building Information Modeling (BIM)", 300, arc_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("ARC401", "Architectural Design Studio V", 400, arc_dept, 2, Course.ExamType.WRITTEN, 180),
                ("ARC403", "Advanced Building Technology & Working Drawings", 400, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC405", "Professional Architectural Practice & Management", 400, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC407", "Urban Design & Housing Studies", 400, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC499", "Architectural Research Dissertation", 400, arc_dept, 1, Course.ExamType.WRITTEN, 120),
                ("ARC501", "Terminal Comprehensive Design Studio", 500, arc_dept, 2, Course.ExamType.WRITTEN, 180),
                ("ARC503", "Sustainable & Ecological Architecture", 500, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC505", "Advanced Building Construction Technology", 500, arc_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ARC599", "Terminal Thesis Project & Defense", 500, arc_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Geography and Environmental Management (GEO) ===
                ("GEO101", "Introduction to Physical Geography", 100, geo_dept, 2, Course.ExamType.CBT, 60),
                ("GEO103", "Introduction to Human Geography", 100, geo_dept, 2, Course.ExamType.CBT, 60),
                ("GEO201", "Geomorphology", 200, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO203", "Climatology and Meteorology", 200, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO205", "Cartography and Map Analysis", 200, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO301", "Hydrology and Water Resources Management", 300, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO303", "Biogeography and Soil Science", 300, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO305", "GIS and Remote Sensing Applications", 300, geo_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("GEO307", "Research Methods in Environmental Science", 300, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO401", "Advanced Spatial Analysis and Modeling", 400, geo_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("GEO403", "Environmental Hazard & Disaster Risk Management", 400, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO405", "Waste Management and Environmental Pollution", 400, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO407", "Climate Change Adaptation and Policies", 400, geo_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GEO499", "Final Year Research Project in Geography", 400, geo_dept, 1, Course.ExamType.WRITTEN, 120),

                # === Urban and Regional Planning (URP) ===
                ("URP201", "Planning Theory and History", 200, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP203", "Planning Studio I (Site Planning)", 200, urp_dept, 2, Course.ExamType.WRITTEN, 180),
                ("URP301", "Urban Design and Landscape Planning", 300, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP303", "Planning Studio III (Residential Land Use)", 300, urp_dept, 2, Course.ExamType.WRITTEN, 180),
                ("URP305", "Regional Development Planning", 300, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP307", "Transportation Planning and Management", 300, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP401", "Planning Studio V (Master Planning)", 400, urp_dept, 2, Course.ExamType.WRITTEN, 180),
                ("URP403", "Environmental Infrastructure Planning", 400, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP405", "Urban Governance and Planning Law", 400, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP407", "Urban Resilience and Disaster Management", 400, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP499", "Planning Dissertation & Project", 400, urp_dept, 1, Course.ExamType.WRITTEN, 120),
                ("URP501", "Advanced Urban Management & Public Policy", 500, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP503", "Planning Studio VII (Comprehensive Development)", 500, urp_dept, 2, Course.ExamType.WRITTEN, 180),
                ("URP505", "Urban Economics, Real Estate & Municipal Finance", 500, urp_dept, 2, Course.ExamType.WRITTEN, 120),
                ("URP599", "Terminal Master Thesis in Urban Planning", 500, urp_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Estate Management (ESM) ===
                ("ESM201", "Principles of Valuation I", 200, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM203", "Land Economics I", 200, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM301", "Applied Valuation I (Commercial)", 300, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM303", "Property Management and Maintenance I", 300, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM305", "Real Estate Finance & Investment Analysis", 300, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM307", "Urban Land Policy and Administration", 300, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM401", "Advanced Valuation (Statutory & Agricultural)", 400, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM403", "Project Management & Feasibility Studies", 400, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM405", "Plant and Machinery Valuation", 400, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM407", "Real Estate Marketing and Brokerage", 400, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM499", "Research Project in Estate Management", 400, esm_dept, 1, Course.ExamType.WRITTEN, 120),
                ("ESM501", "Portfolio Management & Property Schemes", 500, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM503", "Advanced Property Development & Facility Mgt", 500, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM505", "Professional Practice, Ethics & Real Estate Law", 500, esm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ESM599", "Terminal Research Project in Real Estate", 500, esm_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Quantity Surveying (QTS) ===
                ("QTS201", "Measurement of Simple Building Works I", 200, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS203", "Construction Technology I", 200, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS301", "Measurement of Complex Building Works I", 300, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS303", "Estimating and Cost Analysis for Buildings", 300, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS305", "Conditions of Contract & Construction Procurement", 300, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS307", "Heavy Civil Engineering Measurement I", 300, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS401", "Measurement of Industrial Works", 400, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS403", "Construction Economics and Cost Modeling", 400, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS405", "Cost Control & Project Financial Management", 400, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS407", "Dispute Resolution & Construction Arbitration", 400, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS499", "Research Dissertation in Quantity Surveying", 400, qts_dept, 1, Course.ExamType.WRITTEN, 120),
                ("QTS501", "Advanced Cost Engineering & Project Auditing", 500, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS503", "Value Engineering and Life Cycle Costing", 500, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS505", "Professional Practice & QS Consulting Practice", 500, qts_dept, 2, Course.ExamType.WRITTEN, 120),
                ("QTS599", "Terminal Research Project in Quantity Surveying", 500, qts_dept, 1, Course.ExamType.WRITTEN, 180),
            ]

            dept_course_objs = {}
            for code, title, lvl, dept_ref, occ, exam_t, dur in dept_courses:
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=dept_ref, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                dept_course_objs[code] = c
                if is_new:
                    created_count += 1

            # 4. Access Grants:
            # All ENV departments get GST courses
            for d_code, d_obj in depts.items():
                d_admin = dept_admins.get(d_code, default_initiator)
                for gst_code, gst_c in gst_courses.items():
                    _, g_created = grant_course_access(gst_c, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

            # Shared ENV Common Courses across built environment depts (ARC, URP, ESM, QTS)
            built_env_depts = [arc_dept, urp_dept, esm_dept, qts_dept]
            for c_code, c_obj in env_course_objs.items():
                target_depts = built_env_depts if c_code != "ENV301" else list(depts.values())
                for d_obj in target_depts:
                    if d_obj:
                        d_admin = dept_admins.get(d_obj.code, default_initiator)
                        _, g_created = grant_course_access(c_obj, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created:
                            grant_count += 1

            # 5. Inter-faculty Course Sharing (MTH101, PHY101, PHY107, ECO101)
            ext_courses = {
                c.code: c
                for c in Course.objects.filter(
                    code__in=["MTH101", "PHY101", "PHY107", "ECO101"],
                    owning_school=school
                )
            }

            # ARC, URP, QTS take MTH101, PHY101, PHY107
            for d_code in ["ARC", "URP", "QTS"]:
                d_obj = depts.get(d_code)
                if d_obj:
                    d_admin = dept_admins.get(d_code, default_initiator)
                    for c_code in ["MTH101", "PHY101", "PHY107"]:
                        if c_code in ext_courses:
                            _, g_created = grant_course_access(ext_courses[c_code], d_obj, initiated_by=default_initiator, decided_by=d_admin)
                            if g_created:
                                grant_count += 1

            # ESM takes ECO101, MTH101
            if esm_dept:
                esm_admin = dept_admins.get("ESM", default_initiator)
                for c_code in ["ECO101", "MTH101"]:
                    if c_code in ext_courses:
                        _, g_created = grant_course_access(ext_courses[c_code], esm_dept, initiated_by=default_initiator, decided_by=esm_admin)
                        if g_created:
                            grant_count += 1

            # GEO takes MTH101, PHY101
            if geo_dept:
                geo_admin = dept_admins.get("GEO", default_initiator)
                for c_code in ["MTH101", "PHY101"]:
                    if c_code in ext_courses:
                        _, g_created = grant_course_access(ext_courses[c_code], geo_dept, initiated_by=default_initiator, decided_by=geo_admin)
                        if g_created:
                            grant_count += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Environmental Science Course Seeding Complete! ==="))
            self.stdout.write(f"New courses created: {created_count}")
            self.stdout.write(f"Course access grants created/verified: {grant_count}")

