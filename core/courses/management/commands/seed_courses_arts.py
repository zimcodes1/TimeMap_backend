"""
Management command to seed courses and access grants for the Faculty of Arts (ARTS)
at NSUK for the current active semester.

Departments:
- English and Literary Studies (ELS) -> Programs: ELSGEN, ELSLIT (Literature in English)
- History and International Studies (HIS) -> Programs: HISGEN, HISDIP (Diplomatic Studies)
- Theatre and Media Arts (TMA) -> Programs: TMAGEN, TMAFLM (Film and Media Studies)
- Languages and Linguistics (LIN) -> Programs: LINGEN, LINFRN (French), LINARB (Arabic)
- Philosophy and Religious Studies (PRS) -> Programs: PRSGEN, PRSCRS (CRS), PRSIRS (IRS)

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
    help = "Seed courses and access grants for Faculty of Arts (ARTS) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Arts (ARTS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ARTS").first()
            if not faculty:
                self.stderr.write("Faculty ARTS not found!")
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
            arts_courses_def = [
                # English & Literary Studies (ELS)
                ("ELS101", "Spoken English and Phonetics", 100, "ELS", 2, Course.ExamType.CBT, 60),
                ("ELS103", "Introduction to English Grammar", 100, "ELS", 2, Course.ExamType.CBT, 60),
                ("ELS105", "Introduction to Prose and Drama", 100, "ELS", 2, Course.ExamType.CBT, 60),
                ("ELS201", "Advanced English Syntax", 200, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS203", "Survey of English Literature", 200, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS301", "Phonology of English", 300, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS303", "African Literature I (Prose)", 300, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS401", "Semantics of English", 400, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS403", "Literary Stylistics", 400, "ELS", 2, Course.ExamType.WRITTEN, 120),
                ("ELS499", "Research Project in English", 400, "ELS", 1, Course.ExamType.WRITTEN, 120),

                # History and International Studies (HIS)
                ("HIS101", "Nigeria: Earliest Times to 1800", 100, "HIS", 2, Course.ExamType.CBT, 60),
                ("HIS103", "Africa and the Wider World", 100, "HIS", 2, Course.ExamType.CBT, 60),
                ("HIS201", "Nigeria: 1800 to 1960", 200, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS203", "Diplomatic History of Europe", 200, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS301", "International Relations in 20th Century", 300, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS303", "Economic History of West Africa", 300, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS401", "Nigerian Foreign Policy Since 1960", 400, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS403", "Philosophy and Historiography", 400, "HIS", 2, Course.ExamType.WRITTEN, 120),
                ("HIS499", "Research Project in History", 400, "HIS", 1, Course.ExamType.WRITTEN, 120),

                # Theatre and Media Arts (TMA)
                ("TMA101", "Introduction to Drama and Theatre", 100, "TMA", 2, Course.ExamType.CBT, 60),
                ("TMA103", "Acting Techniques and Body Expression", 100, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA201", "Playwriting I", 200, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA203", "Stagecraft, Lighting & Scenery Design", 200, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA301", "Directing for the Stage I", 300, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA303", "African Theatre and Cultural Performance", 300, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA401", "Theatre Management and Entrepreneurship", 400, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA403", "Advanced Production Workshop", 400, "TMA", 2, Course.ExamType.WRITTEN, 120),
                ("TMA499", "Practical / Research Project in Theatre", 400, "TMA", 1, Course.ExamType.WRITTEN, 120),

                # Languages and Linguistics (LIN)
                ("LIN101", "Introduction to Linguistics I", 100, "LIN", 2, Course.ExamType.CBT, 60),
                ("LIN103", "Introduction to Phonetics & Phonology", 100, "LIN", 2, Course.ExamType.CBT, 60),
                ("LIN201", "Morphology and Syntax I", 200, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN203", "Semantics and Pragmatics Basics", 200, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN301", "Sociolinguistics", 300, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN303", "Historical and Comparative Linguistics", 300, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN401", "Psycholinguistics", 400, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN403", "Applied Linguistics & Language Teaching", 400, "LIN", 2, Course.ExamType.WRITTEN, 120),
                ("LIN499", "Research Project in Linguistics", 400, "LIN", 1, Course.ExamType.WRITTEN, 120),

                # Philosophy and Religious Studies (PRS)
                ("PRS101", "Introduction to Philosophy I", 100, "PRS", 2, Course.ExamType.CBT, 60),
                ("PRS103", "Introduction to Ethics and Moral Reasoning", 100, "PRS", 2, Course.ExamType.CBT, 60),
                ("PRS201", "Ancient and Medieval Philosophy", 200, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS203", "Logic and Critical Thinking I", 200, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS301", "Epistemology: Theories of Knowledge", 300, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS303", "African Philosophy", 300, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS401", "Metaphysics: Nature of Reality", 400, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS403", "Philosophy of Religion", 400, "PRS", 2, Course.ExamType.WRITTEN, 120),
                ("PRS499", "Research Project in Philosophy", 400, "PRS", 1, Course.ExamType.WRITTEN, 120),
            ]

            for code, title, lvl, dept_code, occ, exam_t, dur in arts_courses_def:
                d = depts.get(dept_code)
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=d, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                if is_new: created_count += 1

            # 3. Program-Specific Specializations
            # Literature in English (ELSLIT) under ELS
            els_dept = depts.get("ELS")
            if els_dept:
                lit_prog = els_dept.programs.filter(code="ELSLIT").first()
                if lit_prog:
                    for code, title, lvl in [
                        ("LIT301", "Literary Theory and Criticism", 300),
                        ("LIT401", "Modern African Poetry and Drama", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, els_dept, faculty, school, active_semester, target_program=lit_prog)
                        if is_new: created_count += 1

            # Diplomatic Studies (HISDIP) under HIS
            his_dept = depts.get("HIS")
            if his_dept:
                dip_prog = his_dept.programs.filter(code="HISDIP").first()
                if dip_prog:
                    for code, title, lvl in [
                        ("DIP301", "Diplomatic Practice, Protocol & Etiquette", 300),
                        ("DIP401", "International Conflict Resolution & Negotiation", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, his_dept, faculty, school, active_semester, target_program=dip_prog)
                        if is_new: created_count += 1

            # Film and Media Studies (TMAFLM) under TMA
            tma_dept = depts.get("TMA")
            if tma_dept:
                flm_prog = tma_dept.programs.filter(code="TMAFLM").first()
                if flm_prog:
                    for code, title, lvl in [
                        ("FLM301", "Film Production Techniques & Cinematography", 300),
                        ("FLM401", "Screenplay Writing & Video Editing", 400),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, tma_dept, faculty, school, active_semester, target_program=flm_prog)
                        if is_new: created_count += 1

            # French (LINFRN) & Arabic (LINARB) under LIN
            lin_dept = depts.get("LIN")
            if lin_dept:
                frn_prog = lin_dept.programs.filter(code="LINFRN").first()
                if frn_prog:
                    for code, title, lvl in [
                        ("FRN101", "Elementary French Grammar & Phonetics I", 100),
                        ("FRN201", "Intermediate French Grammar & Composition", 200),
                        ("FRN301", "Advanced French Composition & Oral Practice", 300),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, lin_dept, faculty, school, active_semester, target_program=frn_prog)
                        if is_new: created_count += 1

                arb_prog = lin_dept.programs.filter(code="LINARB").first()
                if arb_prog:
                    for code, title, lvl in [
                        ("ARB101", "Elementary Arabic Grammar & Phonology I", 100),
                        ("ARB201", "Intermediate Arabic Syntax & Reading", 200),
                        ("ARB301", "Arabic Literary Texts and Translation", 300),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, lin_dept, faculty, school, active_semester, target_program=arb_prog)
                        if is_new: created_count += 1

            # CRS (PRSCRS) & IRS (PRSIRS) under PRS
            prs_dept = depts.get("PRS")
            if prs_dept:
                crs_prog = prs_dept.programs.filter(code="PRSCRS").first()
                if crs_prog:
                    for code, title, lvl in [
                        ("CRS101", "Introduction to Old Testament Literature", 100),
                        ("CRS201", "Early Church History to 451 AD", 200),
                        ("CRS301", "Pauline Epistles & Theology", 300),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, prs_dept, faculty, school, active_semester, target_program=crs_prog)
                        if is_new: created_count += 1

                irs_prog = prs_dept.programs.filter(code="PRSIRS").first()
                if irs_prog:
                    for code, title, lvl in [
                        ("IRS101", "Introduction to Qur'anic Sciences", 100),
                        ("IRS201", "Studies on Hadith Literature", 200),
                        ("IRS301", "Islamic Jurisprudence (Fiqh) I", 300),
                    ]:
                        c, is_new = ensure_course(code, title, lvl, prs_dept, faculty, school, active_semester, target_program=irs_prog)
                        if is_new: created_count += 1

            # 4. Grants: GST to all Arts Departments
            for d in depts.values():
                d_admin = dept_admins.get(d.code) or default_initiator
                for gst_code in ["GST111", "GST113", "GST115", "GST211", "GST221", "GST311"]:
                    gst = gst_courses.get(gst_code)
                    if gst:
                        _, g_created = grant_course_access(gst, d, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created: grant_count += 1

            # 5. Inter-Departmental Arts Sharing
            faculty_sharing = [
                ("ELS101", ["HIS", "TMA", "LIN", "PRS"]),
                ("HIS101", ["ELS", "TMA", "PRS"]),
                ("PRS101", ["ELS", "HIS", "LIN"]),
                ("TMA101", ["ELS", "LIN"]),
                ("LIN101", ["ELS"]),
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

        self.stdout.write(self.style.SUCCESS("=== Faculty of Arts Course Seeding Complete! ==="))
        self.stdout.write(f"New courses created: {created_count}")
        self.stdout.write(f"Course access grants created/verified: {grant_count}")

