"""
Management command to seed courses and access grants for the Faculty of Social Sciences (FSS)
at NSUK for the current active semester.

Departments:
- Economics (ECO) -> Programs: ECOGEN, ECODEV (Development Economics)
- Political Science (POL) -> Programs: POLGEN, POLINT (International Relations)
- Sociology (SOC) -> Programs: SOCGEN, SOCCRM (Criminology & Security Studies)
- Mass Communication (MAC) -> Programs: MACGEN, MACBRD (Broadcasting), MACADV (PR & Advertising)
- Psychology (PSY) -> Programs: PSYGEN

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
    help = "Seed courses and access grants for Faculty of Social Sciences (FSS) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Social Sciences (FSS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FSS").first()
            if not faculty:
                self.stderr.write("Faculty FSS not found!")
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

            # 2. Departmental Core Courses
            fss_courses_def = [
                # Economics (ECO)
                ("ECO101", "Principles of Economics I (Micro)", 100, "ECO", 2, Course.ExamType.CBT, 60),
                ("ECO103", "Mathematics for Economists I", 100, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO201", "Macroeconomic Theory I", 200, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO203", "Microeconomic Theory I", 200, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO205", "Mathematics for Economists II", 200, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO301", "Introduction to Econometrics", 300, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO303", "Public Sector Economics", 300, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO305", "International Economics I", 300, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO401", "Advanced Microeconomics", 400, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO403", "Economic Planning & Policy", 400, "ECO", 2, Course.ExamType.WRITTEN, 120),
                ("ECO499", "Research Project in Economics", 400, "ECO", 1, Course.ExamType.WRITTEN, 120),

                # Political Science (POL)
                ("POL101", "Introduction to Political Science", 100, "POL", 2, Course.ExamType.CBT, 60),
                ("POL103", "Nigerian Constitutional Development", 100, "POL", 2, Course.ExamType.CBT, 60),
                ("POL201", "Political Ideas & Ideologies", 200, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL203", "Nigerian Government and Politics I", 200, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL205", "Introduction to Political Analysis", 200, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL301", "Comparative Politics", 300, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL303", "Public Opinion and Voting Behaviour", 300, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL305", "Theories of International Relations", 300, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL401", "State and Economy", 400, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL403", "Political Behaviour & Social Movements", 400, "POL", 2, Course.ExamType.WRITTEN, 120),
                ("POL499", "Research Project in Political Science", 400, "POL", 1, Course.ExamType.WRITTEN, 120),

                # Sociology (SOC)
                ("SOC101", "Introduction to Sociology I", 100, "SOC", 2, Course.ExamType.CBT, 60),
                ("SOC103", "Introduction to Social Anthropology", 100, "SOC", 2, Course.ExamType.CBT, 60),
                ("SOC201", "Classical Sociological Theory", 200, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC203", "Social Change and Development", 200, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC205", "Sociology of the Family", 200, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC301", "Methods of Social Research I", 300, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC303", "Sociology of Crime and Delinquency", 300, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC305", "Formal Organizations", 300, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC401", "Contemporary Sociological Theory", 400, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC403", "Urban Sociology & Demography", 400, "SOC", 2, Course.ExamType.WRITTEN, 120),
                ("SOC499", "Research Project in Sociology", 400, "SOC", 1, Course.ExamType.WRITTEN, 120),

                # Mass Communication (MAC)
                ("MAC101", "Introduction to Mass Communication", 100, "MAC", 2, Course.ExamType.CBT, 60),
                ("MAC103", "Writing for the Mass Media", 100, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC201", "News Writing and Reporting", 200, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC203", "Media Law and Ethics", 200, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC205", "Broadcast Production Basics", 200, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC301", "Mass Communication Theories", 300, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC303", "Development Communication", 300, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC305", "Investigative and Interpretative Journalism", 300, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC401", "Media Management and Economics", 400, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC403", "Digital Journalism & New Media Technologies", 400, "MAC", 2, Course.ExamType.WRITTEN, 120),
                ("MAC499", "Research / Practical Production Project in Mass Comm", 400, "MAC", 1, Course.ExamType.WRITTEN, 120),

                # Psychology (PSY)
                ("PSY101", "Introduction to Psychology I", 100, "PSY", 2, Course.ExamType.CBT, 60),
                ("PSY103", "Physiological Psychology I", 100, "PSY", 2, Course.ExamType.CBT, 60),
                ("PSY201", "Developmental Psychology I", 200, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY203", "Social Psychology I", 200, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY205", "General Experimental Psychology", 200, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY301", "Cognitive Psychology", 300, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY303", "Psychological Testing and Measurement", 300, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY305", "Abnormal Psychology I", 300, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY401", "Clinical Psychology I", 400, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY403", "Organizational Psychology", 400, "PSY", 2, Course.ExamType.WRITTEN, 120),
                ("PSY499", "Research Project in Psychology", 400, "PSY", 1, Course.ExamType.WRITTEN, 120),
            ]

            for code, title, lvl, dept_code, occ, exam_t, dur in fss_courses_def:
                d = depts.get(dept_code)
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=d, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                if is_new: created_count += 1

            # 3. Program-Specific Specializations
            # Development Economics (ECODEV)
            eco_dept = depts.get("ECO")
            if eco_dept:
                dev_prog = eco_dept.programs.filter(code="ECODEV").first()
                if dev_prog:
                    for code, title, lvl in [
                        ("DEV301", "Theories of Economic Development", 300),
                        ("DEV401", "Project Analysis, Monitoring & Evaluation", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, eco_dept, faculty, school, active_semester, target_program=dev_prog)
                        if is_new: created_count += 1

            # International Relations (POLINT)
            pol_dept = depts.get("POL")
            if pol_dept:
                int_prog = pol_dept.programs.filter(code="POLINT").first()
                if int_prog:
                    for code, title, lvl in [
                        ("INT301", "International Organizations and Global Governance", 300),
                        ("INT401", "Contemporary Strategic and Security Studies", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, pol_dept, faculty, school, active_semester, target_program=int_prog)
                        if is_new: created_count += 1

            # Criminology and Security Studies (SOCCRM)
            soc_dept = depts.get("SOC")
            if soc_dept:
                crm_prog = soc_dept.programs.filter(code="SOCCRM").first()
                if crm_prog:
                    for code, title, lvl in [
                        ("CRM301", "Criminological Theories and Penology", 300),
                        ("CRM401", "Criminal Justice Systems and Human Rights", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, soc_dept, faculty, school, active_semester, target_program=crm_prog)
                        if is_new: created_count += 1

            # Broadcasting (MACBRD) & PR/Adv (MACADV)
            mac_dept = depts.get("MAC")
            if mac_dept:
                brd_prog = mac_dept.programs.filter(code="MACBRD").first()
                if brd_prog:
                    for code, title, lvl in [
                        ("BRD301", "Radio Production and Programming Techniques", 300),
                        ("BRD401", "Television Production and Studio Directing", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, mac_dept, faculty, school, active_semester, target_program=brd_prog)
                        if is_new: created_count += 1

                adv_prog = mac_dept.programs.filter(code="MACADV").first()
                if adv_prog:
                    for code, title, lvl in [
                        ("ADV301", "Principles of Advertising and Brand Strategy", 300),
                        ("ADV401", "Public Relations Campaign Planning and Execution", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, mac_dept, faculty, school, active_semester, target_program=adv_prog)
                        if is_new: created_count += 1

            # 4. Grants: GST to all FSS Departments
            for d in depts.values():
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115", "GST211", "GST221", "GST311"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 5. Inter-Departmental Social Science Sharing within FSS
            fss_sharing = [
                ("ECO101", ["POL", "SOC", "MAC", "PSY"]),
                ("POL101", ["ECO", "SOC", "MAC", "PSY"]),
                ("SOC101", ["ECO", "POL", "MAC", "PSY"]),
                ("PSY101", ["SOC", "MAC"]),
                ("SOC203", ["POL", "ECO"]),
            ]
            for course_code, target_codes in fss_sharing:
                c = Course.objects.filter(code=course_code).first()
                if not c: continue
                owner_admin = dept_admins.get(c.owning_department.code if c.owning_department else "") or default_initiator
                for t_code in target_codes:
                    t_dept = depts.get(t_code)
                    if t_dept and t_dept.id != c.owning_department_id:
                        t_admin = dept_admins.get(t_code) or default_initiator
                        _, g_created = grant_course_access(c, t_dept, initiated_by=owner_admin, decided_by=t_admin)
                        if g_created: grant_count += 1

            # 6. External Grants to FSS: Statistics (STA101) & Computing (COS101) from FNAS
            for ext_code, target_codes in [
                ("STA101", ["ECO", "SOC", "PSY"]),
                ("COS101", ["MAC", "ECO"]),
            ]:
                c = Course.objects.filter(code=ext_code).first()
                if c:
                    for t_code in target_codes:
                        t_dept = depts.get(t_code)
                        if t_dept:
                            t_admin = dept_admins.get(t_code) or default_initiator
                            _, g_created = grant_course_access(c, t_dept, initiated_by=default_initiator, decided_by=t_admin)
                            if g_created: grant_count += 1

        self.stdout.write(self.style.SUCCESS("=== Faculty of Social Sciences Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

