"""
Management command to seed courses and access grants for the Faculty of Natural and
Applied Sciences (FNAS) at NSUK for the current active semester.

Ensures:
- No duplicate common courses (reuses GST111, MTH101, PHY101, etc.).
- Departmental & Program-specific courses for CMP (SWE, CYS), SLT, STA, BCH, MCB, ZOO, MTH, PHY (ELX), CHM (IND).
- Course caps per level: 100L <= 10, 200L <= 8, 300L <= 7, 400L <= 6.
- Cross-departmental approved CourseAccessGrants.
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
    help = "Seed courses and access grants for FNAS (Natural & Applied Sciences) for the active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Natural & Applied Sciences (FNAS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FNAS").first()
            if not faculty:
                self.stderr.write("Faculty FNAS not found!")
                return

            active_semester = get_active_semester(school)
            if not active_semester:
                self.stderr.write("No active semester found! Please activate a semester first.")
                return

            school_admin, fac_admin, dept_admins = resolve_scope_admins(school, faculty)
            default_initiator = fac_admin or school_admin

            # 1. Ensure University GST Courses
            gst_courses = ensure_general_studies_courses(school, active_semester, default_initiator)

            # Department mapping
            depts = {d.code: d for d in faculty.departments.all()}

            # Track counts
            created_count = 0
            grant_count = 0

            # 2. Foundation Science Courses Owned by FNAS Departments
            foundation_courses = [
                # Mathematics
                ("MTH101", "Elementary Mathematics I (Algebra & Trigonometry)", 100, "MTH", 2, Course.ExamType.CBT, 60),
                ("MTH103", "Vectors, Geometry and Trigonometry", 100, "MTH", 2, Course.ExamType.CBT, 60),
                ("MTH201", "Mathematical Methods I", 200, "MTH", 2, Course.ExamType.WRITTEN, 120),
                ("MTH203", "Sets, Logic and Modern Algebra", 200, "MTH", 2, Course.ExamType.WRITTEN, 120),
                ("MTH301", "Abstract Algebra I", 300, "MTH", 2, Course.ExamType.WRITTEN, 120),
                ("MTH303", "Real Analysis I", 300, "MTH", 2, Course.ExamType.WRITTEN, 120),
                ("MTH401", "Theory of Ordinary Differential Equations", 400, "MTH", 2, Course.ExamType.WRITTEN, 120),
                ("MTH499", "Research Project in Mathematics", 400, "MTH", 1, Course.ExamType.WRITTEN, 120),

                # Physics
                ("PHY101", "General Physics I (Mechanics & Thermal)", 100, "PHY", 2, Course.ExamType.CBT, 60),
                ("PHY107", "General Physics Practical Laboratory I", 100, "PHY", 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("PHY201", "Modern Physics I", 200, "PHY", 2, Course.ExamType.WRITTEN, 120),
                ("PHY203", "Electric Circuit Theory & Electronics", 200, "PHY", 2, Course.ExamType.WRITTEN, 120),
                ("PHY301", "Electromagnetism I", 300, "PHY", 2, Course.ExamType.WRITTEN, 120),
                ("PHY303", "Quantum Mechanics I", 300, "PHY", 2, Course.ExamType.WRITTEN, 120),
                ("PHY401", "Solid State Physics I", 400, "PHY", 2, Course.ExamType.WRITTEN, 120),
                ("PHY499", "Research Project in Physics", 400, "PHY", 1, Course.ExamType.WRITTEN, 120),

                # Chemistry
                ("CHM101", "General Chemistry I (Inorganic & Physical)", 100, "CHM", 2, Course.ExamType.CBT, 60),
                ("CHM107", "General Chemistry Practical Laboratory I", 100, "CHM", 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("CHM201", "Inorganic Chemistry I", 200, "CHM", 2, Course.ExamType.WRITTEN, 120),
                ("CHM203", "Organic Chemistry I", 200, "CHM", 2, Course.ExamType.WRITTEN, 120),
                ("CHM301", "Physical Chemistry II", 300, "CHM", 2, Course.ExamType.WRITTEN, 120),
                ("CHM303", "Applied Spectroscopy", 300, "CHM", 2, Course.ExamType.WRITTEN, 120),
                ("CHM401", "Advanced Analytical Chemistry", 400, "CHM", 2, Course.ExamType.WRITTEN, 120),
                ("CHM499", "Research Project in Chemistry", 400, "CHM", 1, Course.ExamType.WRITTEN, 120),

                # Zoology / Biology
                ("BIO101", "General Biology I (Cells & Diversity)", 100, "ZOO", 2, Course.ExamType.CBT, 60),
                ("BIO107", "General Biology Practical Laboratory I", 100, "ZOO", 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("ZOO201", "Invertebrate Zoology", 200, "ZOO", 2, Course.ExamType.WRITTEN, 120),
                ("ZOO203", "Chordate Zoology", 200, "ZOO", 2, Course.ExamType.WRITTEN, 120),
                ("ZOO301", "Animal Physiology I", 300, "ZOO", 2, Course.ExamType.WRITTEN, 120),
                ("ZOO303", "Entomology I", 300, "ZOO", 2, Course.ExamType.WRITTEN, 120),
                ("ZOO401", "Parasitology & Public Health", 400, "ZOO", 2, Course.ExamType.WRITTEN, 120),
                ("ZOO499", "Research Project in Zoology", 400, "ZOO", 1, Course.ExamType.WRITTEN, 120),

                # Computer Science
                ("COS101", "Introduction to Computing", 100, "CMP", 2, Course.ExamType.CBT, 60),
                ("COS103", "Principles of Programming I", 100, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS105", "Algorithms & Logic", 100, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS201", "Computer Programming II (OOP)", 200, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS203", "Discrete Structures", 200, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS205", "Data Structures & Algorithms", 200, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS301", "Database Systems I", 300, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS303", "Operating Systems", 300, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS305", "Computer Networks & Data Comm", 300, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS401", "Artificial Intelligence & Machine Learning", 400, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS403", "Software Engineering Principles", 400, "CMP", 2, Course.ExamType.WRITTEN, 120),
                ("COS499", "Research Project in Computer Science", 400, "CMP", 1, Course.ExamType.WRITTEN, 120),

                # Statistics
                ("STA101", "Elementary Statistics I", 100, "STA", 2, Course.ExamType.CBT, 60),
                ("STA103", "Probability Theory I", 100, "STA", 2, Course.ExamType.CBT, 60),
                ("STA201", "Mathematical Statistics I", 200, "STA", 2, Course.ExamType.WRITTEN, 120),
                ("STA203", "Statistical Inference I", 200, "STA", 2, Course.ExamType.WRITTEN, 120),
                ("STA301", "Distribution Theory", 300, "STA", 2, Course.ExamType.WRITTEN, 120),
                ("STA303", "Multivariate Analysis I", 300, "STA", 2, Course.ExamType.WRITTEN, 120),
                ("STA401", "Advanced Probability Theory", 400, "STA", 2, Course.ExamType.WRITTEN, 120),
                ("STA499", "Research Project in Statistics", 400, "STA", 1, Course.ExamType.WRITTEN, 120),

                # Biochemistry
                ("BCH101", "General Biochemistry I", 100, "BCH", 2, Course.ExamType.CBT, 60),
                ("BCH201", "Chemistry of Biomolecules", 200, "BCH", 2, Course.ExamType.WRITTEN, 120),
                ("BCH301", "Enzymology I", 300, "BCH", 2, Course.ExamType.WRITTEN, 120),
                ("BCH303", "Metabolism of Carbohydrates & Lipids", 300, "BCH", 2, Course.ExamType.WRITTEN, 120),
                ("BCH401", "Advanced Biochemical Methods", 400, "BCH", 2, Course.ExamType.WRITTEN, 120),
                ("BCH499", "Research Project in Biochemistry", 400, "BCH", 1, Course.ExamType.WRITTEN, 120),

                # Microbiology
                ("MCB101", "Introduction to Microbiology", 100, "MCB", 2, Course.ExamType.CBT, 60),
                ("MCB201", "General Microbiology I", 200, "MCB", 2, Course.ExamType.WRITTEN, 120),
                ("MCB301", "Bacteriology & Virology", 300, "MCB", 2, Course.ExamType.WRITTEN, 120),
                ("MCB303", "Immunology & Immunochemistry", 300, "MCB", 2, Course.ExamType.WRITTEN, 120),
                ("MCB401", "Industrial Microbiology & Biotechnology", 400, "MCB", 2, Course.ExamType.WRITTEN, 120),
                ("MCB499", "Research Project in Microbiology", 400, "MCB", 1, Course.ExamType.WRITTEN, 120),

                # Science Lab Tech (SLT)
                ("SLT101", "Laboratory Safety and Management", 100, "SLT", 2, Course.ExamType.CBT, 60),
                ("SLT201", "Basic Instrumentation & Measurement", 200, "SLT", 2, Course.ExamType.WRITTEN, 120),
                ("SLT301", "Laboratory Design and Planning", 300, "SLT", 2, Course.ExamType.WRITTEN, 120),
                ("SLT401", "Advanced Instrumental Analysis", 400, "SLT", 2, Course.ExamType.WRITTEN, 120),
                ("SLT499", "Research Project in SLT", 400, "SLT", 1, Course.ExamType.WRITTEN, 120),
            ]

            seeded_courses = {}
            for code, title, lvl, dept_code, occ, exam_t, dur in foundation_courses:
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
                seeded_courses[code] = c
                if is_new:
                    created_count += 1

            # 3. Program-Specific Specializations
            # CMP: Cybersecurity (CYS) & Software Engineering (SWE)
            cmp_dept = depts.get("CMP")
            if cmp_dept:
                cys_prog = cmp_dept.programs.filter(code__in=["CMPCYS", "CYB"]).first()
                swe_prog = cmp_dept.programs.filter(code__in=["CMPSWE", "SWE"]).first()

                if cys_prog:
                    cys_courses = [
                        ("CYS201", "Introduction to Cybersecurity", 200, 2),
                        ("CYS301", "Information Security & Cryptography", 300, 2),
                        ("CYS401", "Ethical Hacking & Penetration Testing", 400, 2),
                    ]
                    for code, title, lvl, occ in cys_courses:
                        c, is_new = ensure_course(code, title, lvl, cmp_dept, faculty, school, active_semester, occurrences=occ, target_program=cys_prog)
                        seeded_courses[code] = c
                        if is_new: created_count += 1

                if swe_prog:
                    swe_courses = [
                        ("SWE201", "Software Requirements Engineering", 200, 2),
                        ("SWE301", "Software Architecture & Design", 300, 2),
                        ("SWE401", "Software Quality Assurance & Testing", 400, 2),
                    ]
                    for code, title, lvl, occ in swe_courses:
                        c, is_new = ensure_course(code, title, lvl, cmp_dept, faculty, school, active_semester, occurrences=occ, target_program=swe_prog)
                        seeded_courses[code] = c
                        if is_new: created_count += 1

            # PHY: Physics with Electronics (PHYELX)
            phy_dept = depts.get("PHY")
            if phy_dept:
                elx_prog = phy_dept.programs.filter(code="PHYELX").first()
                if elx_prog:
                    for code, title, lvl in [
                        ("ELX201", "Solid State Electronics I", 200),
                        ("ELX301", "Microprocessor Systems & Architecture", 300),
                        ("ELX401", "Digital Signal Processing in Electronics", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, phy_dept, faculty, school, active_semester, target_program=elx_prog)
                        seeded_courses[code] = c
                        if is_new: created_count += 1

            # CHM: Industrial Chemistry (CHMIND)
            chm_dept = depts.get("CHM")
            if chm_dept:
                ind_prog = chm_dept.programs.filter(code__in=["CHMIND", "INDCHM"]).first()
                if ind_prog:
                    for code, title, lvl in [
                        ("ICH201", "Chemical Process Calculations", 200),
                        ("ICH301", "Industrial Chemical Technology I", 300),
                        ("ICH401", "Polymer & Petroleum Chemistry", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, chm_dept, faculty, school, active_semester, target_program=ind_prog)
                        seeded_courses[code] = c
                        if is_new: created_count += 1

            # 4. Cross-Departmental Access Grants (Approved Sharing)
            # Level 100 GST sharing to all FNAS departments
            for d in depts.values():
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1
                for gst_code in ["GST211", "GST221"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1
                gst311 = gst_courses.get("GST311")
                if gst311:
                    _, g_created = grant_course_access(gst311, d, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created: grant_count += 1

            # Inter-Departmental Science Course Grants:
            sharing_matrix = [
                # MTH101 shared to CMP, STA, PHY, CHM, SLT
                ("MTH101", ["CMP", "STA", "PHY", "CHM", "SLT"]),
                ("MTH103", ["CMP", "STA", "PHY"]),
                ("MTH201", ["CMP", "STA", "PHY"]),
                # PHY101 & PHY107 shared to CMP, MTH, CHM, SLT
                ("PHY101", ["CMP", "MTH", "CHM", "SLT"]),
                ("PHY107", ["CMP", "MTH", "CHM", "SLT"]),
                ("PHY201", ["MTH"]),
                # CHM101 & CHM107 shared to BCH, MCB, ZOO, SLT
                ("CHM101", ["BCH", "MCB", "ZOO", "SLT"]),
                ("CHM107", ["BCH", "MCB", "ZOO", "SLT"]),
                # BIO101 & BIO107 shared to BCH, MCB, SLT
                ("BIO101", ["BCH", "MCB", "SLT"]),
                ("BIO107", ["BCH", "MCB", "SLT"]),
                # COS101 shared to STA, MTH, PHY, CHM, SLT
                ("COS101", ["STA", "MTH", "PHY", "CHM", "SLT"]),
                # STA101 shared to CMP, MTH, BCH, MCB
                ("STA101", ["CMP", "MTH", "BCH", "MCB"]),
                # BCH201 shared to MCB
                ("BCH201", ["MCB"]),
                # MCB201 shared to BCH
                ("MCB201", ["BCH"]),
            ]

            for course_code, target_dept_codes in sharing_matrix:
                course = Course.objects.filter(code=course_code).first()
                if not course:
                    continue
                owning_dept_admin = dept_admins.get(course.owning_department.code if course.owning_department else "") or default_initiator
                for t_code in target_dept_codes:
                    t_dept = depts.get(t_code)
                    if t_dept and t_dept.id != course.owning_department_id:
                        t_admin = dept_admins.get(t_code) or default_initiator
                        _, g_created = grant_course_access(course, t_dept, initiated_by=owning_dept_admin, decided_by=t_admin)
                        if g_created:
                            grant_count += 1

        self.stdout.write(self.style.SUCCESS(f"=== FNAS Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

