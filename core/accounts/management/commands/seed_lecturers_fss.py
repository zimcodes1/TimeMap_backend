"""
Management command to seed realistic lecturers and course assignments for the Faculty
of Social Sciences (FSS) and its departments (ECO, POL, SOC, MAC, PSY) at NSUK.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.lecturer_seeding_utils import assign_lecturers_to_course, ensure_lecturer
from accounts.models import LecturerStaff
from courses.models import Course
from hierarchy.models import Faculty, School


class Command(BaseCommand):
    help = "Seed lecturers and course assignments for Faculty of Social Sciences (FSS)."

    def add_arguments(self, parser):
        parser.add_argument("--school-code", type=str, default="NSUK")
        parser.add_argument("--default-password", type=str, default="Lecturer#2026")

    def handle(self, *args, **options):
        school_code = options["school_code"]
        password = options["default_password"]
        self.stdout.write(self.style.NOTICE("=== Seeding Lecturers for Faculty of Social Sciences (FSS) ==="))

        with transaction.atomic():
            school = School.objects.filter(code=school_code).first()
            if not school:
                self.stderr.write(f"School {school_code} not found!")
                return

            faculty = Faculty.objects.filter(school=school, code="FSS").first()
            if not faculty:
                self.stderr.write("Faculty FSS not found!")
                return

            depts = {d.code: d for d in faculty.departments.all()}
            eco_dept = depts.get("ECO")
            pol_dept = depts.get("POL")
            soc_dept = depts.get("SOC")
            mac_dept = depts.get("MAC")
            psy_dept = depts.get("PSY")

            lecturers_data = {
                # Economics (ECO)
                "ECO": [
                    ("STAFF_ECO01", "Prof. Sarah O. Anyanwu", "sarah.anyanwu@nsuk.edu.ng"),
                    ("STAFF_ECO02", "Dr. Aliyu A. Sanusi", "aliyu.sanusi@nsuk.edu.ng"),
                    ("STAFF_ECO03", "Dr. Godwin E. Bassey", "godwin.bassey@nsuk.edu.ng"),
                    ("STAFF_ECO04", "Mrs. Zainab O. Ahmed", "zainab.ahmed@nsuk.edu.ng"),
                    ("STAFF_ECO05", "Mr. Peter K. Danladi", "peter.danladi@nsuk.edu.ng"),
                    ("STAFF_ECO06", "Dr. Hauwa C. Mohammed", "hauwa.mohammed@nsuk.edu.ng"),
                ],
                # Political Science (POL)
                "POL": [
                    ("STAFF_POL01", "Prof. Jibrin I. Ibrahim", "jibrin.ibrahim@nsuk.edu.ng"),
                    ("STAFF_POL02", "Dr. Abubakar O. Sulaiman", "abubakar.sulaiman@nsuk.edu.ng"),
                    ("STAFF_POL03", "Dr. Joy N. Ezeilo", "joy.ezeilo@nsuk.edu.ng"),
                    ("STAFF_POL04", "Mr. Timothy K. Bako", "timothy.bako@nsuk.edu.ng"),
                    ("STAFF_POL05", "Mrs. Fatima B. Alkali", "fatima.alkali@nsuk.edu.ng"),
                    ("STAFF_POL06", "Dr. Sunday A. Ocholi", "sunday.ocholi@nsuk.edu.ng"),
                ],
                # Sociology (SOC)
                "SOC": [
                    ("STAFF_SOC01", "Prof. Patrick A. Edewor", "patrick.edewor@nsuk.edu.ng"),
                    ("STAFF_SOC02", "Dr. Halima D. Shuaibu", "halima.shuaibu@nsuk.edu.ng"),
                    ("STAFF_SOC03", "Dr. Victor O. Aigbokhaevbolo", "victor.aigbokhaevbolo@nsuk.edu.ng"),
                    ("STAFF_SOC04", "Mr. Dauda M. Gana", "dauda.gana@nsuk.edu.ng"),
                    ("STAFF_SOC05", "Mrs. Rose C. Ogbu", "rose.ogbu@nsuk.edu.ng"),
                    ("STAFF_SOC06", "Dr. Shehu M. Keffi", "shehu.keffi@nsuk.edu.ng"),
                ],
                # Mass Communication (MAC)
                "MAC": [
                    ("STAFF_MAC01", "Prof. Umaru A. Pate", "umaru.pate@nsuk.edu.ng"),
                    ("STAFF_MAC02", "Dr. Comfort M. Anzaku", "comfort.anzaku.mac@nsuk.edu.ng"),
                    ("STAFF_MAC03", "Dr. James O. Olatunji", "james.olatunji@nsuk.edu.ng"),
                    ("STAFF_MAC04", "Mr. Kenneth I. Dogo", "kenneth.dogo@nsuk.edu.ng"),
                    ("STAFF_MAC05", "Mrs. Aisha T. Jibrin", "aisha.jibrin@nsuk.edu.ng"),
                    ("STAFF_MAC06", "Dr. Benson E. Uche", "benson.uche@nsuk.edu.ng"),
                ],
                # Psychology (PSY)
                "PSY": [
                    ("STAFF_PSY01", "Prof. Andrew E. Zamani", "andrew.zamani@nsuk.edu.ng"),
                    ("STAFF_PSY02", "Dr. Ruth A. Abiola", "ruth.abiola@nsuk.edu.ng"),
                    ("STAFF_PSY03", "Dr. Mohammed K. Garkuwa", "mohammed.garkuwa@nsuk.edu.ng"),
                    ("STAFF_PSY04", "Mr. Emmanuel S. Kalu", "emmanuel.kalu.psy@nsuk.edu.ng"),
                    ("STAFF_PSY05", "Mrs. Grace O. Adama", "grace.adama@nsuk.edu.ng"),
                    ("STAFF_PSY06", "Dr. David A. Ayuba", "david.ayuba@nsuk.edu.ng"),
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

            # Assign GST221 (Peace Studies & Conflict Resolution) to POL lecturers
            gst221 = Course.objects.filter(owning_school=school, code="GST221").first()
            if gst221 and seeded_lecturers.get("POL"):
                assign_lecturers_to_course(gst221, seeded_lecturers["POL"][:2])

            self.stdout.write(self.style.SUCCESS("=== Faculty of Social Sciences Lecturer Seeding Complete! ==="))
            self.stdout.write(f"New lecturers created: {total_lecturers_created}")
            self.stdout.write(f"Courses assigned: {assigned_courses_count}")

