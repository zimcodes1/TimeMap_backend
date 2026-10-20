import pytest
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, User
from courses.models import Course, CourseAccessGrant
from hierarchy.models import Department, Faculty, School


class ExamOfficerCoursePermissionsTests(APITestCase):
    def setUp(self):
        # Hierarchy
        self.school = School.objects.create(name="Faculty of Science School", code="FSS")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept1 = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.faculty, name="Mathematics", code="MTH")

        # Courses
        self.course_csc = Course.objects.create(
            code="CSC101",
            title="Introduction to CS",
            level=100,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept1,
            exam_type=Course.ExamType.WRITTEN,
            exam_duration_minutes=120,
        )
        self.course_mth = Course.objects.create(
            code="MTH101",
            title="Elementary Mathematics",
            level=100,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept2,
            exam_type=Course.ExamType.WRITTEN,
            exam_duration_minutes=120,
        )

        # 1. Department Admin (without exam officer)
        self.dept_admin_user = User.objects.create_user(
            identifier="CSC_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_admin_user, staff_id="CSC_ADMIN", full_name="CSC Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1, is_exam_officer=False,
        )

        # MTH Admin
        self.mth_admin_user = User.objects.create_user(
            identifier="MTH_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.mth_admin = AdminOfficer.objects.create(
            user=self.mth_admin_user, staff_id="MTH_ADMIN", full_name="MTH Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept2, is_exam_officer=False,
        )

        # Grant MTH101 access to CSC department
        CourseAccessGrant.objects.create(
            course=self.course_mth,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.dept1,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.APPROVED,
            initiated_by=self.mth_admin,
        )

        # 2. Department Exam Officer
        self.eo_user = User.objects.create_user(
            identifier="CSC_EO", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.eo = AdminOfficer.objects.create(
            user=self.eo_user, staff_id="CSC_EO", full_name="CSC Exam Officer",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1, is_exam_officer=True,
        )

        # 3. Faculty Course & Faculty Admins / Exam Officers
        self.course_fac = Course.objects.create(
            code="FSC101",
            title="General Science",
            level=100,
            owning_level=Course.OwningLevel.FACULTY,
            owning_faculty=self.faculty,
            exam_type=Course.ExamType.WRITTEN,
            exam_duration_minutes=120,
        )
        self.fac_admin_user = User.objects.create_user(
            identifier="FSC_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_admin_user, staff_id="FSC_ADMIN", full_name="FSC Admin",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty, is_exam_officer=False,
        )
        self.fac_eo_user = User.objects.create_user(
            identifier="FSC_EO", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.fac_eo = AdminOfficer.objects.create(
            user=self.fac_eo_user, staff_id="FSC_EO", full_name="FSC Exam Officer",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty, is_exam_officer=True,
        )

    def test_exam_officer_cannot_create_course(self):
        self.client.force_authenticate(user=self.eo_user)
        res = self.client.post("/api/courses/courses/", {
            "code": "CSC102",
            "title": "Programming Principles",
            "level": 100,
            "owning_level": "department",
            "owning_department": self.dept1.id,
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_exam_officer_cannot_delete_course(self):
        self.client.force_authenticate(user=self.eo_user)
        res = self.client.delete(f"/api/courses/courses/{self.course_csc.id}/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_exam_officer_cannot_edit_general_course_fields(self):
        self.client.force_authenticate(user=self.eo_user)
        res = self.client.patch(f"/api/courses/courses/{self.course_csc.id}/", {
            "title": "Hacked Title",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Exam officers can only modify exam settings", str(res.data))

    def test_exam_officer_can_modify_exam_settings_on_owned_course(self):
        self.client.force_authenticate(user=self.eo_user)
        # For CBT, sitting window duration is calculated dynamically via throughput metrics and is cleared to None
        res = self.client.patch(f"/api/courses/courses/{self.course_csc.id}/", {
            "exam_type": "cbt",
            "exam_duration_per_student_minutes": 45,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.course_csc.refresh_from_db()
        self.assertEqual(self.course_csc.exam_type, "cbt")
        self.assertIsNone(self.course_csc.exam_duration_minutes)
        self.assertEqual(self.course_csc.exam_duration_per_student_minutes, 45)

        # For written exam, sitting window duration is set and per_student is None
        res = self.client.patch(f"/api/courses/courses/{self.course_csc.id}/", {
            "exam_type": "written",
            "exam_duration_minutes": 150,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.course_csc.refresh_from_db()
        self.assertEqual(self.course_csc.exam_type, "written")
        self.assertEqual(self.course_csc.exam_duration_minutes, 150)
        self.assertIsNone(self.course_csc.exam_duration_per_student_minutes)

    def test_faculty_admin_and_officer_cannot_configure_department_course(self):
        # 1. Faculty Exam Officer cannot edit department course
        self.client.force_authenticate(user=self.fac_eo_user)
        res = self.client.patch(f"/api/courses/courses/{self.course_csc.id}/", {
            "exam_type": "written",
            "exam_duration_minutes": 90,
        })
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

        # 2. Faculty Admin cannot edit department course
        self.client.force_authenticate(user=self.fac_admin_user)
        res = self.client.patch(f"/api/courses/courses/{self.course_csc.id}/", {
            "exam_type": "written",
            "exam_duration_minutes": 90,
        })
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

        # 3. Representation for faculty exam officer should mark department course as can_edit_exam_settings = False
        res = self.client.get("/api/courses/courses/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        courses = res.data if isinstance(res.data, list) else res.data.get("results", [])
        csc_course = next((c for c in courses if c["id"] == self.course_csc.id), None)
        self.assertIsNotNone(csc_course)
        self.assertFalse(csc_course["can_edit_exam_settings"])

    def test_faculty_officer_can_configure_faculty_course(self):
        self.client.force_authenticate(user=self.fac_eo_user)
        res = self.client.patch(f"/api/courses/courses/{self.course_fac.id}/", {
            "exam_type": "cbt",
            "exam_duration_per_student_minutes": 60,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.course_fac.refresh_from_db()
        self.assertEqual(self.course_fac.exam_type, "cbt")
        self.assertIsNone(self.course_fac.exam_duration_minutes)
        self.assertEqual(self.course_fac.exam_duration_per_student_minutes, 60)

        # In list representation, faculty officer can edit faculty course
        res = self.client.get("/api/courses/courses/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        courses = res.data if isinstance(res.data, list) else res.data.get("results", [])
        fac_course = next((c for c in courses if c["id"] == self.course_fac.id), None)
        self.assertIsNotNone(fac_course)
        self.assertTrue(fac_course["can_edit_exam_settings"])

    def test_exam_officer_cannot_edit_granted_course(self):
        self.client.force_authenticate(user=self.eo_user)
        # MTH101 is granted to CSC, not owned by CSC
        res = self.client.patch(f"/api/courses/courses/{self.course_mth.id}/", {
            "exam_type": "cbt",
            "exam_duration_minutes": 180,
        })
        # Should be forbidden by object permissions (or validation error)
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST])

    def test_course_representation_flags_for_granted_and_owned_courses(self):
        self.client.force_authenticate(user=self.eo_user)
        res = self.client.get("/api/courses/courses/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        courses = res.data if isinstance(res.data, list) else res.data.get("results", [])

        csc_data = next((c for c in courses if c["id"] == self.course_csc.id), None)
        mth_data = next((c for c in courses if c["id"] == self.course_mth.id), None)

        self.assertIsNotNone(csc_data)
        self.assertFalse(csc_data["is_granted_to_scope"])
        self.assertTrue(csc_data["can_edit_exam_settings"])

        self.assertIsNotNone(mth_data)
        self.assertTrue(mth_data["is_granted_to_scope"])
        self.assertFalse(mth_data["can_edit_exam_settings"])

    def test_exam_settings_access_endpoint(self):
        # 1. As exam officer
        self.client.force_authenticate(user=self.eo_user)
        res = self.client.get("/api/courses/courses/exam-settings-access/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["is_exam_officer"])
        self.assertTrue(res.data["has_scope_exam_officer"])
        self.assertTrue(res.data["can_access_exam_tab"])

        # 2. As dept admin with an exam officer in their scope
        self.client.force_authenticate(user=self.dept_admin_user)
        res = self.client.get("/api/courses/courses/exam-settings-access/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_exam_officer"])
        self.assertTrue(res.data["has_scope_exam_officer"])
        self.assertFalse(res.data["can_access_exam_tab"])

        # 3. Deactivate or remove the exam officer: now dept admin gets can_access_exam_tab = True
        self.eo.user.is_active = False
        self.eo.user.save()
        res = self.client.get("/api/courses/courses/exam-settings-access/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["has_scope_exam_officer"])
        self.assertTrue(res.data["can_access_exam_tab"])
