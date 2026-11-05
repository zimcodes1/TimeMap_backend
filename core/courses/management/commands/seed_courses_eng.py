"""
Management command to seed courses and access grants for the Faculty of Engineering (ENG)
at NSUK for the current active semester.

Departments:
- Civil Engineering (CVE, 500L) -> CVEGEN, CVEWTR
- Electrical and Electronics Engineering (EEE, 500L) -> EEEGEN, EEETEL
- Mechanical Engineering (MEE, 500L) -> MEEGEN, MEEAUT
- Chemical Engineering (CHE, 500L) -> CHEGEN

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
    help = "Seed courses and access grants for Faculty of Engineering (ENG) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Engineering (ENG) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENG").first()
            if not faculty:
                self.stderr.write("Faculty ENG not found!")
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

            cve_dept = depts.get("CVE")
            eee_dept = depts.get("EEE")
            mee_dept = depts.get("MEE")
            che_dept = depts.get("CHE")

            # 2. Faculty-wide General Engineering Courses
            eng_core_courses = [
                # 100L
                ("ENG101", "Engineering Drawing I (Technical Drawing)", 100, cve_dept, 2, Course.ExamType.WRITTEN, 120),

                # 200L
                ("ENG201", "Applied Mechanics I (Statics)", 200, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENG203", "Engineering Thermodynamics I", 200, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENG205", "Fluid Mechanics I", 200, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENG207", "Materials Science & Engineering", 200, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENG209", "Basic Electrical Engineering (Circuits)", 200, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ENG211", "Engineering Workshop Practice", 200, mee_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),

                # 300L
                ("ENG301", "Engineering Mathematics III", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),

                # 400L
                ("ENG401", "Engineering Economics & Management", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),

                # 500L
                ("ENG501", "Engineering Law, Ethics & Professional Practice", 500, cve_dept, 2, Course.ExamType.WRITTEN, 120),
            ]

            eng_course_objs = {}
            for code, title, lvl, dept_ref, occ, exam_t, dur in eng_core_courses:
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=dept_ref, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                eng_course_objs[code] = c
                if is_new:
                    created_count += 1

            # 3. Department Specific Discipline Courses
            dept_courses = [
                # === Civil Engineering (CVE) ===
                ("CVE301", "Theory of Structures I", 300, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE303", "Soil Mechanics I & Engineering Geology", 300, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE305", "Hydraulics and Hydrology", 300, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE307", "Civil Engineering Materials & Concrete", 300, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE309", "Surveying for Civil Engineers", 300, cve_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),

                ("CVE401", "Design of Reinforced Concrete Structures I", 400, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE403", "Highway & Transportation Engineering I", 400, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE405", "Foundation Engineering I", 400, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE407", "Water Resources & Environmental Sanitation", 400, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE409", "Civil Engineering Drawing & CAD Detailing", 400, cve_dept, 2, Course.ExamType.WRITTEN, 120),

                ("CVE501", "Design of Structural Steel and Timber", 500, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE503", "Water Supply and Wastewater Engineering", 500, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE505", "Construction Project Management & Contracts", 500, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE507", "Bridge and Drainage Engineering", 500, cve_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CVE599", "Final Year Civil Engineering Project & Defense", 500, cve_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Electrical and Electronics Engineering (EEE) ===
                ("EEE301", "Electromagnetic Field Theory", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE303", "Analogue Electronic Circuits", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE305", "Electric Power Principles & Machines I", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE307", "Digital Electronics & Microprocessors", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE309", "Signals and Linear Systems", 300, eee_dept, 2, Course.ExamType.WRITTEN, 120),

                ("EEE401", "Communication Principles & Systems", 400, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE403", "Control Systems Engineering I", 400, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE405", "Power Electronics and Drives", 400, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE407", "Electric Power Transmission & Distribution", 400, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE409", "Embedded Systems and Microcontrollers", 400, eee_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),

                ("EEE501", "Advanced Power System Analysis & Security", 500, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE503", "Wireless and Mobile Communication Networks", 500, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE505", "Modern Control Engineering & Robotics", 500, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE507", "Renewable Energy Systems and Smart Grids", 500, eee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EEE599", "Final Year Electrical Project & Defense", 500, eee_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Mechanical Engineering (MEE) ===
                ("MEE301", "Mechanics of Machines I (Dynamics)", 300, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE303", "Strength of Materials I", 300, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE305", "Applied Thermodynamics II (Heat Engines)", 300, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE307", "Manufacturing Technology & Machine Tools", 300, mee_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("MEE309", "Machine Design I & CAD Analysis", 300, mee_dept, 2, Course.ExamType.WRITTEN, 120),

                ("MEE401", "Heat and Mass Transfer", 400, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE403", "Fluid Machinery and Turbo-Machines", 400, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE405", "Mechanical Vibrations & Acoustic Control", 400, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE407", "Internal Combustion Engines & Power Plants", 400, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE409", "Metallurgy & Heat Treatment of Metals", 400, mee_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),

                ("MEE501", "Advanced Machine Design and Optimization", 500, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE503", "Automotive Engineering & Chassis Systems", 500, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE505", "HVAC & Refrigeration Systems", 500, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE507", "Mechatronics & Industrial Automation", 500, mee_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MEE599", "Final Year Mechanical Project & Defense", 500, mee_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Chemical Engineering (CHE) ===
                ("CHE301", "Chemical Engineering Thermodynamics I", 300, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE303", "Transport Phenomena (Fluid & Heat Transfer)", 300, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE305", "Chemical Reaction Kinetics & Reactor Design", 300, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE307", "Particulate Technology & Separations", 300, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE309", "Process Analysis & Instrumentation", 300, che_dept, 2, Course.ExamType.WRITTEN, 120),

                ("CHE401", "Chemical Reaction Engineering II", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE403", "Mass Transfer Operations & Distillation", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE405", "Process Dynamics and Control", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE407", "Petroleum Refining & Petrochemicals", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE409", "Biochemical Engineering Fundamentals", 400, che_dept, 2, Course.ExamType.WRITTEN, 120),

                ("CHE501", "Chemical Plant Design & Economics", 500, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE503", "Polymer Science and Engineering", 500, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE505", "Environmental Pollution Control in Process Ind", 500, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE507", "Process Modeling & Optimization", 500, che_dept, 2, Course.ExamType.WRITTEN, 120),
                ("CHE599", "Final Year Chemical Project & Defense", 500, che_dept, 1, Course.ExamType.WRITTEN, 180),
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
            # GSTs for all Engineering departments
            for d_code, d_obj in depts.items():
                d_admin = dept_admins.get(d_code, default_initiator)
                for gst_code, gst_c in gst_courses.items():
                    _, g_created = grant_course_access(gst_c, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

            # Shared General Engineering courses across all departments
            all_eng_depts = list(depts.values())
            for c_code, c_obj in eng_course_objs.items():
                for d_obj in all_eng_depts:
                    if d_obj:
                        d_admin = dept_admins.get(d_obj.code, default_initiator)
                        _, g_created = grant_course_access(c_obj, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created:
                            grant_count += 1

            # 5. Inter-faculty Course Sharing (MTH101, PHY101, PHY107, CHM101, CHM107, COS101, MTH201, COS201)
            fnas_courses = {
                c.code: c
                for c in Course.objects.filter(
                    code__in=["MTH101", "PHY101", "PHY107", "CHM101", "CHM107", "COS101", "MTH201", "COS201"],
                    owning_school=school
                )
            }

            # All 4 departments take 100L science foundations
            foundation_100l = ["MTH101", "PHY101", "PHY107", "CHM101", "CHM107", "COS101"]
            for d_obj in all_eng_depts:
                d_admin = dept_admins.get(d_obj.code, default_initiator)
                for c_code in foundation_100l:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], d_obj, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created:
                            grant_count += 1

                # 200L: MTH201 for all engineering
                if "MTH201" in fnas_courses:
                    _, g_created = grant_course_access(fnas_courses["MTH201"], d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

            # EEE takes COS201
            if eee_dept and "COS201" in fnas_courses:
                eee_admin = dept_admins.get("EEE", default_initiator)
                _, g_created = grant_course_access(fnas_courses["COS201"], eee_dept, initiated_by=default_initiator, decided_by=eee_admin)
                if g_created:
                    grant_count += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Engineering Course Seeding Complete! ==="))
            self.stdout.write(f"New courses created: {created_count}")
            self.stdout.write(f"Course access grants created/verified: {grant_count}")

