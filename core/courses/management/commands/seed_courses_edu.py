"""
Management command to seed courses and access grants for the Faculty of Education (EDU)
at NSUK for the current active semester.

Departments:
- Educational Foundations (EDF) -> Programs: EDFECE, EDFGEN
- Science, Technology and Mathematics Education (STM) -> Programs: STMCHM, STMCMP, STMMTH, STMPHY, STMGEN
- Arts and Social Science Education (ASE) -> Programs: ASEGEN, ASEECO, ASESOC
- Guidance and Counselling (GAC) -> Programs: GACGEN

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
    help = "Seed courses and access grants for Faculty of Education (EDU) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Education (EDU) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="EDU").first()
            if not faculty:
                self.stderr.write("Faculty EDU not found!")
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

            edf_dept = depts.get("EDF")
            stm_dept = depts.get("STM")
            ase_dept = depts.get("ASE")
            gac_dept = depts.get("GAC")

            # 2. Faculty-wide Professional Education Courses (assigned under EDF)
            edu_core_courses = [
                # 100 Level
                ("EDU101", "Introduction to Teaching Profession", 100, edf_dept, 2, Course.ExamType.CBT, 60),
                ("EDU103", "History of Education in Nigeria", 100, edf_dept, 2, Course.ExamType.CBT, 60),
                ("EDU105", "Philosophical Foundations of Education", 100, edf_dept, 2, Course.ExamType.CBT, 60),

                # 200 Level
                ("EDU201", "Curriculum and Instruction I", 200, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EDU203", "Educational Psychology & Child Development", 200, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EDU205", "Sociological Foundations of Education", 200, edf_dept, 2, Course.ExamType.WRITTEN, 120),

                # 300 Level
                ("EDU301", "Teaching Practice I", 300, edf_dept, 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("EDU303", "Educational Research Methods & Statistics", 300, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EDU305", "Educational Technology & ICT in Education", 300, edf_dept, 2, Course.ExamType.WRITTEN, 120),

                # 400 Level
                ("EDU401", "Teaching Practice II", 400, edf_dept, 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("EDU403", "Educational Administration and Planning", 400, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EDU405", "Measurement, Testing and Evaluation", 400, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("EDU499", "Final Year Research Project in Education", 400, edf_dept, 1, Course.ExamType.WRITTEN, 120),
            ]

            edu_course_objs = {}
            for code, title, lvl, dept_ref, occ, exam_t, dur in edu_core_courses:
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=dept_ref, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                edu_course_objs[code] = c
                if is_new:
                    created_count += 1

            # 3. Department Specific Courses
            dept_courses = [
                # Early Childhood Education (EDF)
                ("ECE101", "Child Development in Early Years", 100, edf_dept, 2, Course.ExamType.CBT, 60),
                ("ECE201", "Early Childhood Curriculum & Play Methods", 200, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ECE203", "Health, Safety and Nutrition for Children", 200, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ECE301", "Organization of Early Childhood Centers", 300, edf_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ECE401", "Inclusive Classrooms & Special Needs in ECE", 400, edf_dept, 2, Course.ExamType.WRITTEN, 120),

                # Science, Tech & Math Education (STM)
                ("STM201", "Laboratory Design and Safety in Science Teaching", 200, stm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("STM301", "Curriculum and Methods in Science & Math Ed", 300, stm_dept, 2, Course.ExamType.WRITTEN, 120),
                ("STM401", "Contemporary Issues in Science Education", 400, stm_dept, 2, Course.ExamType.WRITTEN, 120),

                # Arts & Social Science Education (ASE)
                ("SSE101", "Foundations of Social Studies Education", 100, ase_dept, 2, Course.ExamType.CBT, 60),
                ("SSE201", "Socio-Cultural Environment of Nigeria", 200, ase_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ASE301", "Curriculum and Methods of Arts & Social Sciences", 300, ase_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ASE401", "Seminar in Arts & Social Science Education", 400, ase_dept, 2, Course.ExamType.WRITTEN, 120),

                # Guidance & Counselling (GAC)
                ("GAC101", "Principles & Practice of Guidance and Counselling", 100, gac_dept, 2, Course.ExamType.CBT, 60),
                ("GAC201", "Theories of Counselling and Psychotherapy", 200, gac_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GAC203", "Appraisal Techniques & Psychological Testing", 200, gac_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GAC301", "Group Guidance Dynamics and Procedures", 300, gac_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GAC303", "Career Development & Occupational Information", 300, gac_dept, 2, Course.ExamType.WRITTEN, 120),
                ("GAC401", "Counselling Practicum and Clinical Case Study", 400, gac_dept, 1, Course.ExamType.LAB_PRACTICAL, 120),
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
            # All EDU departments get GST courses & EDU core courses
            for d_code, d_obj in depts.items():
                d_admin = dept_admins.get(d_code, default_initiator)

                # GSTs
                for gst_code, gst_c in gst_courses.items():
                    _, g_created = grant_course_access(gst_c, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

                # EDU Core courses
                for edu_code, edu_c in edu_course_objs.items():
                    _, g_created = grant_course_access(edu_c, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

            # 5. Inter-faculty Course Sharing for Education Programs
            # Fetch existing courses from FNAS / ADMIN / FSS
            fnas_courses = {
                c.code: c
                for c in Course.objects.filter(
                    code__in=["CHM101", "CHM107", "CHM201", "COS101", "COS201", "MTH101", "MTH201", "PHY101", "PHY107", "PHY201"],
                    owning_school=school
                )
            }
            fss_courses = {
                c.code: c
                for c in Course.objects.filter(
                    code__in=["ECO101", "ECO201"],
                    owning_school=school
                )
            }

            # Program-specific sharing
            programs = {p.code: p for p in Program.objects.filter(department__faculty=faculty)}

            # STMCHM -> CHM101, CHM107, CHM201
            chm_prog = programs.get("STMCHM")
            if chm_prog and stm_dept:
                stm_admin = dept_admins.get("STM", default_initiator)
                for c_code in ["CHM101", "CHM107", "CHM201"]:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], stm_dept, target_program=chm_prog, initiated_by=default_initiator, decided_by=stm_admin)
                        if g_created:
                            grant_count += 1

            # STMCMP -> COS101, COS201
            cmp_prog = programs.get("STMCMP")
            if cmp_prog and stm_dept:
                stm_admin = dept_admins.get("STM", default_initiator)
                for c_code in ["COS101", "COS201"]:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], stm_dept, target_program=cmp_prog, initiated_by=default_initiator, decided_by=stm_admin)
                        if g_created:
                            grant_count += 1

            # STMMTH -> MTH101, MTH201
            mth_prog = programs.get("STMMTH")
            if mth_prog and stm_dept:
                stm_admin = dept_admins.get("STM", default_initiator)
                for c_code in ["MTH101", "MTH201"]:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], stm_dept, target_program=mth_prog, initiated_by=default_initiator, decided_by=stm_admin)
                        if g_created:
                            grant_count += 1

            # STMPHY -> PHY101, PHY107, PHY201
            phy_prog = programs.get("STMPHY")
            if phy_prog and stm_dept:
                stm_admin = dept_admins.get("STM", default_initiator)
                for c_code in ["PHY101", "PHY107", "PHY201"]:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], stm_dept, target_program=phy_prog, initiated_by=default_initiator, decided_by=stm_admin)
                        if g_created:
                            grant_count += 1

            # ASEECO -> ECO101, ECO201
            eco_prog = programs.get("ASEECO")
            if eco_prog and ase_dept:
                ase_admin = dept_admins.get("ASE", default_initiator)
                for c_code in ["ECO101", "ECO201"]:
                    if c_code in fss_courses:
                        _, g_created = grant_course_access(fss_courses[c_code], ase_dept, target_program=eco_prog, initiated_by=default_initiator, decided_by=ase_admin)
                        if g_created:
                            grant_count += 1

            # ASESOC -> SSE101, SSE201
            soc_prog = programs.get("ASESOC")
            if soc_prog and ase_dept:
                ase_admin = dept_admins.get("ASE", default_initiator)
                for c_code in ["SSE101", "SSE201"]:
                    if c_code in dept_course_objs:
                        _, g_created = grant_course_access(dept_course_objs[c_code], ase_dept, target_program=soc_prog, initiated_by=default_initiator, decided_by=ase_admin)
                        if g_created:
                            grant_count += 1

            # EDFECE -> ECE courses
            ece_prog = programs.get("EDFECE")
            if ece_prog and edf_dept:
                edf_admin = dept_admins.get("EDF", default_initiator)
                for c_code in ["ECE101", "ECE201", "ECE203", "ECE301", "ECE401"]:
                    if c_code in dept_course_objs:
                        _, g_created = grant_course_access(dept_course_objs[c_code], edf_dept, target_program=ece_prog, initiated_by=default_initiator, decided_by=edf_admin)
                        if g_created:
                            grant_count += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Education Course Seeding Complete! ==="))
            self.stdout.write(f"New courses created: {created_count}")
            self.stdout.write(f"Course access grants created/verified: {grant_count}")
