from accounts.models import AdminOfficer, Student, User, LecturerStaff
from courses.models import Course, CourseAccessGrant, CourseRegistration
from courses.services import get_visible_courses_for_student
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase


class CourseAndVisibilityTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="University", code="UNI")
        self.faculty1 = Faculty.objects.create(school=self.school, name="Faculty 1", code="F1")
        self.faculty2 = Faculty.objects.create(school=self.school, name="Faculty 2", code="F2")

        self.dept1 = Department.objects.create(faculty=self.faculty1, name="CS Dept", code="CS")
        self.dept2 = Department.objects.create(faculty=self.faculty2, name="Math Dept", code="MTH")

        self.student_user = User.objects.create_user(identifier="STU1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student = Student.objects.create(user=self.student_user, matric_number="STU1", full_name="Student 1", department=self.dept1, level=100)

        self.admin_user = User.objects.create_user(identifier="ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM1", full_name="Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept2)

        # Create courses
        self.cs_course = Course.objects.create(code="CSC101", title="Intro to CS", level=100, owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.dept1)
        self.mth_course = Course.objects.create(code="MTH101", title="Calculus I", level=100, owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.dept2)
        self.general_course = Course.objects.create(code="GST101", title="Use of English", level=100, owning_level=Course.OwningLevel.GENERAL)

    def test_default_course_visibility_for_student(self):
        visible = get_visible_courses_for_student(self.student)
        visible_ids = list(visible.values_list("id", flat=True))

        self.assertIn(self.cs_course.id, visible_ids)
        self.assertIn(self.general_course.id, visible_ids)
        self.assertNotIn(self.mth_course.id, visible_ids)

    def test_approved_course_access_grant_expands_visibility(self):
        # Create approved access grant for Math course to CS Dept
        CourseAccessGrant.objects.create(
            course=self.mth_course,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.dept1,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.APPROVED,
            initiated_by=self.admin,
        )

        visible = get_visible_courses_for_student(self.student)
        visible_ids = list(visible.values_list("id", flat=True))
        self.assertIn(self.mth_course.id, visible_ids)

    def test_student_course_registration(self):
        self.client.force_authenticate(user=self.student_user)
        url = "/api/courses/registrations/"
        payload = {
            "course": self.cs_course.id,
            "academic_session": "2025/2026",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, msg=f"Error response: {res.data}")
        self.assertEqual(CourseRegistration.objects.count(), 1)

    def test_filter_courses_by_lecturer_param(self):
        # Create a lecturer
        lec_user = User.objects.create_user(identifier="LEC1", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        lec = LecturerStaff.objects.create(user=lec_user, staff_id="LEC1", full_name="Lecturer 1", department=self.dept2)

        # Assign lecturer to mth_course only
        self.mth_course.lecturers.add(lec)

        # Admin logs in and queries all courses
        self.client.force_authenticate(user=self.admin_user)
        res_all = self.client.get("/api/courses/courses/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        # Without param, admin sees all courses in dept2
        self.assertIn(self.mth_course.id, [c["id"] for c in res_all.data])

        # Query with ?lecturer=<lec.id>
        res_filtered = self.client.get(f"/api/courses/courses/?lecturer={lec.id}")
        self.assertEqual(res_filtered.status_code, status.HTTP_200_OK)
        filtered_ids = [c["id"] for c in res_filtered.data]
        self.assertIn(self.mth_course.id, filtered_ids)
        self.assertNotIn(self.cs_course.id, filtered_ids)

    def test_courses_visibility_for_lecturer_user(self):
        lec_user = User.objects.create_user(identifier="LEC2", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        lec = LecturerStaff.objects.create(user=lec_user, staff_id="LEC2", full_name="Lecturer 2", department=self.dept2)
        self.mth_course.lecturers.add(lec)

        self.client.force_authenticate(user=lec_user)
        res = self.client.get("/api/courses/courses/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = [c["id"] for c in res.data]
        self.assertEqual(returned_ids, [self.mth_course.id])

    def test_department_admin_sees_granted_and_faculty_and_general_courses(self):
        # Admin is department officer in dept2 (Math)
        # Create a faculty-level course under faculty2
        faculty_course = Course.objects.create(
            code="SCI101",
            title="Integrated Science",
            level=100,
            owning_level=Course.OwningLevel.FACULTY,
            owning_faculty=self.faculty2,
        )

        # Create access grant from dept1 (CS) to dept2 (Math) for cs_course
        CourseAccessGrant.objects.create(
            course=self.cs_course,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.dept2,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.APPROVED,
            initiated_by=self.admin,
        )

        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get("/api/courses/courses/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        course_ids = [c["id"] for c in res.data]

        # dept2 owns mth_course
        self.assertIn(self.mth_course.id, course_ids)
        # dept2 is granted cs_course
        self.assertIn(self.cs_course.id, course_ids)
        # faculty2 owns faculty_course
        self.assertIn(faculty_course.id, course_ids)
        # general course
        self.assertIn(self.general_course.id, course_ids)

