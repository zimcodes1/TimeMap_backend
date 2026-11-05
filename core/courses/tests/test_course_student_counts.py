from accounts.models import AdminOfficer, Student, User
from courses.models import Course, CourseAccessGrant, CourseRegistration
from courses.serializers import CourseSerializer
from courses.services import (
    annotate_courses_with_student_counts,
    calculate_course_student_count,
    get_course_attributed_programs,
)
from hierarchy.models import Department, Faculty, Program, School
from rest_framework import status
from rest_framework.test import APITestCase
from student_counts.models import ProgramStudentCount


class CourseStudentCountsTests(APITestCase):
    def setUp(self):
        # 1. School, Faculty, Departments
        self.school = School.objects.create(name="School of Science", code="SOS")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Computing", code="FOC")
        self.cs_dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.math_dept = Department.objects.create(faculty=self.faculty, name="Mathematics", code="MTH")

        # 2. Programs
        self.cs_prog = Program.objects.create(department=self.cs_dept, name="Computer Science", code="CS")
        self.cyber_prog = Program.objects.create(department=self.cs_dept, name="Cybersecurity", code="CYS")
        self.math_prog = Program.objects.create(department=self.math_dept, name="Mathematics", code="MTH")

        # 3. Student populations (ProgramStudentCount)
        # CS dept: 200L CS has 120, 200L Cyber has 40 (Total 200L CS dept = 160)
        # Math dept: 200L Math has 90
        ProgramStudentCount.objects.create(program=self.cs_prog, level=200, count=120)
        ProgramStudentCount.objects.create(program=self.cyber_prog, level=200, count=40)
        ProgramStudentCount.objects.create(program=self.math_prog, level=200, count=90)

        # 4. Admin user
        self.admin_user = User.objects.create_user(
            identifier="ADMIN_CS", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.admin = AdminOfficer.objects.create(
            user=self.admin_user, staff_id="ADMIN_CS", full_name="CS Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.cs_dept,
        )

        # 5. Courses
        self.cs_general_course = Course.objects.create(
            code="CSC201",
            title="Data Structures",
            level=200,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.cs_dept,
            program_scope=Course.ProgramScope.GENERAL,
        )

        self.cs_program_course = Course.objects.create(
            code="CYS201",
            title="Intro to Cyber Defense",
            level=200,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.cs_dept,
            program_scope=Course.ProgramScope.PROGRAM,
            target_program=self.cyber_prog,
        )

    def test_originating_department_general_course_counts_all_programs(self):
        """A general department course counts all programs in the owning department for that level."""
        count = calculate_course_student_count(self.cs_general_course)
        # 120 (CS) + 40 (Cyber) = 160
        self.assertEqual(count, 160)

        # Serializer should reflect this count
        serializer = CourseSerializer(self.cs_general_course)
        self.assertEqual(serializer.data["registration_count"], 160)

    def test_originating_program_scoped_course_counts_only_target_program(self):
        """A program-scoped course only counts students in the target program."""
        count = calculate_course_student_count(self.cs_program_course)
        # Only 40 from cyber_prog
        self.assertEqual(count, 40)

        serializer = CourseSerializer(self.cs_program_course)
        self.assertEqual(serializer.data["registration_count"], 40)

    def test_pending_and_rejected_access_grants_do_not_affect_count(self):
        """Only approved grants add students; pending and rejected grants are ignored."""
        grant = CourseAccessGrant.objects.create(
            course=self.cs_general_course,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.math_dept,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.PENDING,
            initiated_by=self.admin,
        )
        self.assertEqual(calculate_course_student_count(self.cs_general_course), 160)

        grant.status = CourseAccessGrant.Status.REJECTED
        grant.save()
        self.assertEqual(calculate_course_student_count(self.cs_general_course), 160)

    def test_approved_access_grant_expands_student_count(self):
        """An approved grant to another department includes that department's student population."""
        CourseAccessGrant.objects.create(
            course=self.cs_general_course,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.math_dept,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.APPROVED,
            initiated_by=self.admin,
        )
        # 160 (CS dept) + 90 (Math dept) = 250
        count = calculate_course_student_count(self.cs_general_course)
        self.assertEqual(count, 250)

        serializer = CourseSerializer(self.cs_general_course)
        self.assertEqual(serializer.data["registration_count"], 250)

    def test_batch_annotation_matches_individual_calculation(self):
        """annotate_courses_with_student_counts attaches matching cached counts."""
        courses = [self.cs_general_course, self.cs_program_course]
        annotate_courses_with_student_counts(courses)

        self.assertEqual(self.cs_general_course._cached_registration_count, 160)
        self.assertEqual(self.cs_program_course._cached_registration_count, 40)

    def test_course_viewset_list_returns_calculated_student_counts(self):
        """GET /api/courses/courses/ returns accurate registration_count computed in batch."""
        from django.urls import reverse
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get(reverse("course-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        courses_by_code = {item["code"]: item for item in res.data}
        self.assertIn("CSC201", courses_by_code)
        self.assertIn("CYS201", courses_by_code)
        self.assertEqual(courses_by_code["CSC201"]["registration_count"], 160)
        self.assertEqual(courses_by_code["CYS201"]["registration_count"], 40)

    def test_fallback_to_course_registrations_when_no_program_student_counts(self):
        """When no ProgramStudentCount exists, fall back to direct CourseRegistration records."""
        new_course = Course.objects.create(
            code="PHY301",
            title="Advanced Physics",
            level=300,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.cs_dept,
        )
        # No 300L ProgramStudentCount exists for cs_dept
        stu_user = User.objects.create_user(identifier="STU_P1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        stu = Student.objects.create(user=stu_user, matric_number="STU_P1", full_name="Student P1", department=self.cs_dept, level=300)
        CourseRegistration.objects.create(student=stu, course=new_course, academic_session="2025/2026")

        self.assertEqual(calculate_course_student_count(new_course), 1)

