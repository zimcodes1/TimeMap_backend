"""
Management command to seed courses and access grants for the Faculty of Medical and Health Sciences (FMHS)
at NSUK for the current active semester.

Departments:
- Medicine and Surgery (MED, 600L) -> MEDGEN
- Nursing Science (NUR, 500L) -> NURGEN
- Medical Laboratory Science (MLS, 500L) -> MLSGEN
- Public Health (PBH, 400L) -> PBHCOM, PBHGEN

Level limits: 100L <= 10, 200L <= 8, 300L <= 7, 400L <= 6, 500L <= 6, 600L <= 6.
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
    help = "Seed courses and access grants for Faculty of Medical and Health Sciences (FMHS) for active semester."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        self.stdout.write(self.style.NOTICE(f"=== Seeding Courses for Faculty of Medical and Health Sciences (FMHS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FMHS").first()
            if not faculty:
                self.stderr.write("Faculty FMHS not found!")
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

            med_dept = depts.get("MED")
            nur_dept = depts.get("NUR")
            mls_dept = depts.get("MLS")
            pbh_dept = depts.get("PBH")

            # 2. Shared Basic Medical & Pre-clinical Courses (Anatomy, Physiology, Biochemistry, Pathology, Pharmacology)
            shared_medical_courses = [
                # 200L Pre-clinical
                ("ANA201", "Gross Anatomy of Limbs and Thorax", 200, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("ANA203", "Histology and Basic Embryology", 200, med_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("PHS201", "Medical Physiology I (Cardiovascular & Blood)", 200, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PHS203", "Respiratory and Gastrointestinal Physiology", 200, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("BCH201", "General Biochemistry I (Biomolecules)", 200, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("BCH203", "Enzymology and Intermediary Metabolism", 200, med_dept, 2, Course.ExamType.WRITTEN, 120),

                # 300L Clinical Sciences
                ("PTH301", "General and Systemic Pathology I", 300, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PHA301", "General Pharmacology and Toxicology", 300, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MCB301", "Medical Microbiology and Parasitology", 300, med_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
            ]

            shared_course_objs = {}
            for code, title, lvl, dept_ref, occ, exam_t, dur in shared_medical_courses:
                c, is_new = ensure_course(
                    code=code, title=title, level=lvl, department=dept_ref, faculty=faculty, school=school,
                    active_semester=active_semester, occurrences=occ, exam_type=exam_t, exam_duration=dur
                )
                shared_course_objs[code] = c
                if is_new:
                    created_count += 1

            # 3. Department Specific Discipline Courses
            dept_courses = [
                # === Medicine and Surgery (MED) ===
                ("MED301", "Clinical Skills and Medical Examination", 300, med_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("MED303", "Neuroanatomy and Neurophysiology", 300, med_dept, 2, Course.ExamType.WRITTEN, 120),

                ("MED401", "Clinical Medicine I (Cardiology & Pulmonology)", 400, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED403", "Principles of General Surgery I", 400, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED405", "Obstetrics and Gynaecology I", 400, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED407", "Paediatrics and Child Health I", 400, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED409", "Clinical Clerkship and Ward Rounds I", 400, med_dept, 1, Course.ExamType.LAB_PRACTICAL, 180),

                ("MED501", "Clinical Pharmacology and Therapeutics", 500, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED503", "Ophthalmology and ENT Surgery", 500, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED505", "Community Medicine and Epidemiology", 500, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED507", "Mental Health and Behavioural Sciences", 500, med_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MED509", "Clinical Clerkship and Ward Rounds II", 500, med_dept, 1, Course.ExamType.LAB_PRACTICAL, 180),

                ("MED601", "Advanced Clinical Medicine & Therapeutics", 600, med_dept, 2, Course.ExamType.WRITTEN, 180),
                ("MED603", "Advanced Surgery & Operative Techniques", 600, med_dept, 2, Course.ExamType.WRITTEN, 180),
                ("MED605", "Advanced Obstetrics and Gynaecology", 600, med_dept, 2, Course.ExamType.WRITTEN, 180),
                ("MED607", "Advanced Paediatrics & Child Health", 600, med_dept, 2, Course.ExamType.WRITTEN, 180),
                ("MED699", "Final Comprehensive Clinical Examination", 600, med_dept, 1, Course.ExamType.LAB_PRACTICAL, 180),

                # === Nursing Science (NUR) ===
                ("NUR201", "Foundations of Nursing & Nursing Process", 200, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR301", "Medical-Surgical Nursing I", 300, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR303", "Clinical Nursing Practicum I", 300, nur_dept, 1, Course.ExamType.LAB_PRACTICAL, 120),
                ("NUR401", "Maternal and Child Health Nursing I", 400, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR403", "Mental Health and Psychiatric Nursing I", 400, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR405", "Community Health Nursing I", 400, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR407", "Nursing Research Methods and Biostatistics", 400, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR409", "Clinical Nursing Practicum II", 400, nur_dept, 1, Course.ExamType.LAB_PRACTICAL, 180),
                ("NUR501", "Nursing Leadership and Health Administration", 500, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR503", "Advanced Clinical Nursing & Critical Care", 500, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR505", "Teaching and Curriculum in Nursing", 500, nur_dept, 2, Course.ExamType.WRITTEN, 120),
                ("NUR599", "Final Year Research Project in Nursing", 500, nur_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Medical Laboratory Science (MLS) ===
                ("MLS301", "Clinical Chemistry I (Metabolic Disorders)", 300, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS303", "Medical Parasitology and Entomology", 300, mls_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("MLS401", "Haematology and Blood Transfusion I", 400, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS403", "Histopathology and Cytopathology I", 400, mls_dept, 2, Course.ExamType.LAB_PRACTICAL, 120),
                ("MLS405", "Medical Virology and Mycology", 400, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS407", "Advanced Clinical Chemistry Instrumentation", 400, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS409", "Laboratory Management & Quality Assurance", 400, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS501", "Advanced Haematology & Immunohematology", 500, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS503", "Forensic Serology and Toxicology", 500, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS505", "Molecular Diagnostics & Genomics in Pathology", 500, mls_dept, 2, Course.ExamType.WRITTEN, 120),
                ("MLS599", "Final Year Research Project in MLS", 500, mls_dept, 1, Course.ExamType.WRITTEN, 180),

                # === Public Health (PBH) ===
                ("PBH201", "Introduction to Public Health & Primary Care", 200, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH203", "Principles of Epidemiology & Disease Control", 200, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH301", "Biostatistics for Health Sciences", 300, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH303", "Environmental and Occupational Health", 300, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH305", "Maternal and Child Health", 300, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH307", "Health Demography and Vital Statistics", 300, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH401", "Health Policy, Planning and Management", 400, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH403", "Health Economics and Healthcare Financing", 400, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH405", "Public Health Nutrition and Food Security", 400, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH407", "Global Health and Disaster Preparedness", 400, pbh_dept, 2, Course.ExamType.WRITTEN, 120),
                ("PBH499", "Final Year Research Project in Public Health", 400, pbh_dept, 1, Course.ExamType.WRITTEN, 120),
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
            # GSTs for all FMHS departments
            for d_code, d_obj in depts.items():
                d_admin = dept_admins.get(d_code, default_initiator)
                for gst_code, gst_c in gst_courses.items():
                    _, g_created = grant_course_access(gst_c, d_obj, initiated_by=default_initiator, decided_by=d_admin)
                    if g_created:
                        grant_count += 1

            # Sharing of Basic Medical Science Courses:
            # NUR takes ANA201, ANA203, PHS201, BCH201, PTH301, PHA301, MCB301
            nur_grants = ["ANA201", "ANA203", "PHS201", "BCH201", "PTH301", "PHA301", "MCB301"]
            if nur_dept:
                nur_admin = dept_admins.get("NUR", default_initiator)
                for c_code in nur_grants:
                    if c_code in shared_course_objs:
                        _, g_created = grant_course_access(shared_course_objs[c_code], nur_dept, initiated_by=default_initiator, decided_by=nur_admin)
                        if g_created:
                            grant_count += 1

            # MLS takes ANA201, PHS201, PHS203, BCH201, BCH203, PTH301, PHA301, MCB301
            mls_grants = ["ANA201", "PHS201", "PHS203", "BCH201", "BCH203", "PTH301", "PHA301", "MCB301"]
            if mls_dept:
                mls_admin = dept_admins.get("MLS", default_initiator)
                for c_code in mls_grants:
                    if c_code in shared_course_objs:
                        _, g_created = grant_course_access(shared_course_objs[c_code], mls_dept, initiated_by=default_initiator, decided_by=mls_admin)
                        if g_created:
                            grant_count += 1

            # PBH takes PHS201, BCH201
            pbh_grants = ["PHS201", "BCH201"]
            if pbh_dept:
                pbh_admin = dept_admins.get("PBH", default_initiator)
                for c_code in pbh_grants:
                    if c_code in shared_course_objs:
                        _, g_created = grant_course_access(shared_course_objs[c_code], pbh_dept, initiated_by=default_initiator, decided_by=pbh_admin)
                        if g_created:
                            grant_count += 1

            # 5. Inter-faculty Course Sharing (BIO101, BIO107, CHM101, CHM107, PHY101, PHY107, COS101)
            fnas_courses = {
                c.code: c
                for c in Course.objects.filter(
                    code__in=["BIO101", "BIO107", "CHM101", "CHM107", "PHY101", "PHY107", "COS101"],
                    owning_school=school
                )
            }

            pre_med_100l = ["BIO101", "BIO107", "CHM101", "CHM107", "PHY101", "PHY107", "COS101"]
            for d_obj in depts.values():
                d_admin = dept_admins.get(d_obj.code, default_initiator)
                for c_code in pre_med_100l:
                    if c_code in fnas_courses:
                        _, g_created = grant_course_access(fnas_courses[c_code], d_obj, initiated_by=default_initiator, decided_by=d_admin)
                        if g_created:
                            grant_count += 1

            self.stdout.write(self.style.SUCCESS(f"=== Faculty of Medical and Health Sciences Course Seeding Complete! ==="))
            self.stdout.write(f"New courses created: {created_count}")
            self.stdout.write(f"Course access grants created/verified: {grant_count}")

