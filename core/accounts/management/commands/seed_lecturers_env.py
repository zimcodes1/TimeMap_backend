"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Environmental Science (ENV) and its departments (ARC, GEO, URP, ESM, QTS) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Environmental Science (ENV)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Environmental Science (ENV) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="ENV").first()
            if not faculty:
                self.stderr.write("Faculty ENV not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            arc_dept = depts.get("ARC")
            geo_dept = depts.get("GEO")
            urp_dept = depts.get("URP")
            esm_dept = depts.get("ESM")
            qts_dept = depts.get("QTS")

            lecturers_data = {
                # Architecture (ARC)
                "ARC": [
                    ("STAFF_ARC01", "Arc. Prof. Mustapha A. Zubairu", "mustapha.zubairu@nsuk.edu.ng"),
                    ("STAFF_ARC02", "Arc. Dr. Angela N. Okoye", "angela.okoye.arc@nsuk.edu.ng"),
                    ("STAFF_ARC03", "Arc. Dr. Gabriel O. Agbo", "gabriel.agbo@nsuk.edu.ng"),
                    ("STAFF_ARC04", "Arc. Danjuma S. Keffi", "danjuma.keffi.arc@nsuk.edu.ng"),
                    ("STAFF_ARC05", "Arc. Mrs. Zainab B. Aliyu", "zainab.aliyu.arc@nsuk.edu.ng"),
                    ("STAFF_ARC06", "Arc. Solomon C. Eze", "solomon.eze.arc@nsuk.edu.ng"),
                ],
                # Geography and Environmental Management (GEO)
                "GEO": [
                    ("STAFF_GEO01", "Prof. Nasiru M. Idris", "nasiru.idris@nsuk.edu.ng"),
                    ("STAFF_GEO02", "Dr. Rosemary N. Ishaya", "rosemary.ishaya@nsuk.edu.ng"),
                    ("STAFF_GEO03", "Dr. Timothy A. Adewale", "timothy.adewale@nsuk.edu.ng"),
                    ("STAFF_GEO04", "Mr. Abubakar D. Sani", "abubakar.sani.geo@nsuk.edu.ng"),
                    ("STAFF_GEO05", "Mrs. Comfort K. Bako", "comfort.bako.geo@nsuk.edu.ng"),
                    ("STAFF_GEO06", "Dr. Victor M. Gana", "victor.gana@nsuk.edu.ng"),
                ],
                # Urban and Regional Planning (URP)
                "URP": [
                    ("STAFF_URP01", "Tpl. Prof. Olatunji O. Ayeni", "olatunji.ayeni@nsuk.edu.ng"),
                    ("STAFF_URP02", "Tpl. Dr. Fatima M. Alkali", "fatima.alkali.urp@nsuk.edu.ng"),
                    ("STAFF_URP03", "Tpl. Dr. Stephen B. Dogo", "stephen.dogo@nsuk.edu.ng"),
                    ("STAFF_URP04", "Tpl. Mr. Kenneth C. Nnamdi", "kenneth.nnamdi@nsuk.edu.ng"),
                    ("STAFF_URP05", "Tpl. Mrs. Deborah T. Tsado", "deborah.tsado.urp@nsuk.edu.ng"),
                    ("STAFF_URP06", "Tpl. Dr. Musa H. Lafia", "musa.lafia.urp@nsuk.edu.ng"),
                ],
                # Estate Management (ESM)
                "ESM": [
                    ("STAFF_ESM01", "ESV Prof. Charles C. Egolum", "charles.egolum@nsuk.edu.ng"),
                    ("STAFF_ESM02", "ESV Dr. Halima D. Shuaib", "halima.shuaib.esm@nsuk.edu.ng"),
                    ("STAFF_ESM03", "ESV Dr. Paulinus O. Nwafor", "paulinus.nwafor@nsuk.edu.ng"),
                    ("STAFF_ESM04", "ESV Mr. Yakubu M. Bako", "yakubu.bako.esm@nsuk.edu.ng"),
                    ("STAFF_ESM05", "ESV Mrs. Angela S. Kalu", "angela.kalu.esm@nsuk.edu.ng"),
                    ("STAFF_ESM06", "ESV Dr. Emmanuel T. Oche", "emmanuel.oche.esm@nsuk.edu.ng"),
                ],
                # Quantity Surveying (QTS)
                "QTS": [
                    ("STAFF_QTS01", "QS Prof. Deji R. Ogunsemi", "deji.ogunsemi@nsuk.edu.ng"),
                    ("STAFF_QTS02", "QS Dr. Veronica D. Audu", "veronica.audu.qts@nsuk.edu.ng"),
                    ("STAFF_QTS03", "QS Dr. Samson A. Olatunji", "samson.olatunji@nsuk.edu.ng"),
                    ("STAFF_QTS04", "QS Mr. Ibrahim G. Danladi", "ibrahim.danladi.qts@nsuk.edu.ng"),
                    ("STAFF_QTS05", "QS Mrs. Grace O. Eze", "grace.eze.qts@nsuk.edu.ng"),
                    ("STAFF_QTS06", "QS Dr. Aliyu M. Keffi", "aliyu.keffi.qts@nsuk.edu.ng"),
                ],
            }

            seeded_lecturers = {}
            total_lecturers_created = 0

            for d_code, lecs_list in lecturers_data.items():
                dept_obj = depts.get(d_code)
                seeded_lecturers[d_code] = []
                for s_id, name, email in lecs_list:
                    lec, created = ensure_lecturer(s_id, name, email, dept_obj, default_password=password)
                    seeded_lecturers[d_code].append(lec)
                    if created:
                        total_lecturers_created += 1

                all_dept_lecs = list(LecturerStaff.objects.filter(department=dept_obj))
                seeded_lecturers[d_code] = all_dept_lecs

            # Course Assignment Mapping
            assigned_courses_count = 0
            for d_code, dept_obj in depts.items():
                dept_lecs = seeded_lecturers.get(d_code, [])
                if not dept_lecs:
                    continue

                courses = list(Course.objects.filter(owning_department=dept_obj).order_by("level", "code"))
                for idx, course in enumerate(courses):
                    lec1 = dept_lecs[idx % len(dept_lecs)]
                    assigned = [lec1]
                    if course.level <= 200 or course.level >= 400:
                        lec2 = dept_lecs[(idx + 1) % len(dept_lecs)]
                        if lec2 != lec1:
                            assigned.append(lec2)

                    assign_lecturers_to_course(course, assigned)
                    assigned_courses_count += 1

            self.stdout.write(self.style.SUCCESS("=== Faculty of Environmental Science Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

