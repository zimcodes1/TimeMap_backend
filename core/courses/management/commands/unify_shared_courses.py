"""Unifies suffixed courses into canonical shared courses with approved CourseAccessGrants."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import AdminOfficer
from courses.models import Course, CourseAccessGrant
from hierarchy.models import Department, Faculty
from scheduling.models import TimetableEntry


class Command(BaseCommand):
    help = "Unifies duplicated suffixed courses into canonical shared courses with CourseAccessGrants."

    def handle(self, *args, **options):
        with transaction.atomic():
            fnas = Faculty.objects.get(code="FNAS")
            admin = AdminOfficer.objects.filter(scope_faculty=fnas).first()
            if not admin:
                admin = AdminOfficer.objects.filter(level="faculty").first() or AdminOfficer.objects.first()

            depts = {d.code: d for d in fnas.departments.all()}

            # 1. Ensure canonical BIO101 exists by renaming BIO101_Z if needed
            bio101 = Course.objects.filter(code="BIO101").first()
            if not bio101:
                bio101_z = Course.objects.filter(code="BIO101_Z").first()
                if bio101_z:
                    bio101_z.code = "BIO101"
                    bio101_z.title = "General Biology I"
                    bio101_z.owning_level = Course.OwningLevel.DEPARTMENT
                    bio101_z.owning_department = depts.get("ZOO")
                    bio101_z.owning_faculty = fnas
                    bio101_z.save()
                    bio101 = bio101_z
                    self.stdout.write("Renamed BIO101_Z -> BIO101")

            # 2. Configure General Studies (GST) courses as Faculty-level general courses
            gst_courses = {
                "GST111": ("Communication in English I", 100),
                "GST113": ("Nigerian Peoples and Culture", 100),
                "GST115": ("Use of Library & Study Skills", 100),
            }
            for code, (title, level) in gst_courses.items():
                gst = Course.objects.filter(code=code).first()
                if gst:
                    gst.title = title
                    gst.level = level
                    gst.owning_level = Course.OwningLevel.FACULTY
                    gst.owning_faculty = fnas
                    gst.owning_department = None
                    gst.program_scope = Course.ProgramScope.GENERAL
                    gst.exam_type = Course.ExamType.CBT
                    gst.exam_duration_per_student_minutes = 30
                    gst.exam_duration_minutes = None
                    gst.save()
                    self.stdout.write(f"Updated {code} to Faculty-level CBT course.")

            # 3. Ensure STA111 is owned by Statistics
            sta111 = Course.objects.filter(code="STA111").first()
            if sta111 and depts.get("STA"):
                sta111.owning_department = depts["STA"]
                sta111.owning_faculty = fnas
                sta111.exam_type = Course.ExamType.CBT
                sta111.exam_duration_per_student_minutes = 30
                sta111.exam_duration_minutes = None
                sta111.save()
                self.stdout.write("Reassigned STA111 to Statistics department.")

            # 4. Service courses mapping: canonical_code -> (suffixed_codes, [consuming_dept_codes])
            service_mappings = {
                "GST111": (
                    ["GST111_B", "GST111_CH", "GST111_M", "GST111_MT", "GST111_PH", "GST111_S", "GST111_ST", "GST111_Z", "GST-111"],
                    [],  # Faculty-level general course covers all departments automatically
                ),
                "GST113": (
                    ["GST113_B", "GST113_CH", "GST113_M", "GST113_MT", "GST113_PH", "GST113_S", "GST113_ST", "GST113_Z"],
                    [],
                ),
                "GST115": (
                    ["GST115_CH", "GST115_M", "GST115_MT", "GST115_PH", "GST115_Z"],
                    [],
                ),
                "MTH101": (
                    ["MTH101_B", "MTH101_CH", "MTH101_M", "MTH101_PH", "MTH101_S", "MTH101_ST", "MTH101_Z"],
                    ["CMP", "SLT", "STA", "BCH", "MCB", "ZOO", "PHY", "CHM"],
                ),
                "MTH103": (
                    ["MTH103_ST"],
                    ["STA"],
                ),
                "MTH201": (
                    ["MTH201_CH", "MTH201_PH", "MTH201_ST"],
                    ["CMP", "STA", "PHY", "CHM"],
                ),
                "PHY101": (
                    ["PHY101_B", "PHY101_CH", "PHY101_M", "PHY101_MT", "PHY101_S", "PHY101_Z"],
                    ["CMP", "SLT", "MTH", "BCH", "MCB", "ZOO", "CHM"],
                ),
                "CHM101": (
                    ["CHM101_B", "CHM101_M", "CHM101_PH", "CHM101_S", "CHM101_Z"],
                    ["SLT", "BCH", "MCB", "ZOO", "PHY"],
                ),
                "CHM201": (
                    ["CHM201_B"],
                    ["BCH"],
                ),
                "BIO101": (
                    ["BIO101_B", "BIO101_M", "BIO101_S"],
                    ["SLT", "BCH", "MCB"],
                ),
                "BCH201": (
                    ["BCH201_M"],
                    ["MCB"],
                ),
                "MCB201": (
                    ["MCB201_B"],
                    ["BCH"],
                ),
                "STA101": (
                    ["STA101_MT"],
                    ["MTH"],
                ),
                "STA111": (
                    [],
                    ["CMP"],
                ),
                "STA201": (
                    ["STA201_MT", "STA201_S", "STA201_Z"],
                    ["SLT", "MTH", "ZOO"],
                ),
                "COS101": (
                    ["CMP101_CH", "CMP101_MT", "CMP101_PH", "CMP101_ST"],
                    ["STA", "MTH", "PHY", "CHM"],
                ),
            }

            now = timezone.now()
            repointed_entries = 0
            grants_created = 0
            courses_deleted = 0

            for canonical_code, (suffixed_codes, consuming_dept_codes) in service_mappings.items():
                canonical = Course.objects.filter(code=canonical_code).first()
                if not canonical:
                    self.stdout.write(self.style.WARNING(f"Canonical course {canonical_code} not found!"))
                    continue

                # 4a. Re-point TimetableEntry objects and delete suffixed courses
                for suff_code in suffixed_codes:
                    suff_course = Course.objects.filter(code=suff_code).first()
                    if suff_course:
                        updated = TimetableEntry.objects.filter(course=suff_course).update(course=canonical)
                        repointed_entries += updated
                        suff_course.delete()
                        courses_deleted += 1

                # 4b. Create approved CourseAccessGrant for consuming departments
                for dept_code in consuming_dept_codes:
                    dept = depts.get(dept_code)
                    if not dept:
                        continue
                    # Don't grant to owning department
                    if canonical.owning_department_id == dept.id:
                        continue

                    grant, created = CourseAccessGrant.objects.get_or_create(
                        course=canonical,
                        granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
                        granted_to_department=dept,
                        defaults={
                            "direction": CourseAccessGrant.Direction.OFFERED,
                            "status": CourseAccessGrant.Status.APPROVED,
                            "grant_scope": CourseAccessGrant.GrantScope.GENERAL,
                            "initiated_by": admin,
                            "decided_by": admin,
                            "decided_at": now,
                        },
                    )
                    if created:
                        grants_created += 1
                    elif grant.status != CourseAccessGrant.Status.APPROVED:
                        grant.status = CourseAccessGrant.Status.APPROVED
                        grant.decided_at = now
                        grant.save(update_fields=["status", "decided_at"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"Done! Repointed {repointed_entries} timetable entries, created {grants_created} CourseAccessGrants, deleted {courses_deleted} redundant suffixed courses."
                )
            )
