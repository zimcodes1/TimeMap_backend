from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, Student, User
from hierarchy.models import Department, Faculty, School


class ScopedPermissionsTests(APITestCase):
    def setUp(self):
        # Create hierarchy structure
        # School 1
        self.school1 = School.objects.create(name="School of Science", code="SOS")
        self.faculty1 = Faculty.objects.create(school=self.school1, name="Faculty of Physical Sciences", code="FPS")
        self.dept1 = Department.objects.create(faculty=self.faculty1, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.faculty1, name="Mathematics", code="MTH")

        # School 2
        self.school2 = School.objects.create(name="School of Arts", code="SOA")
        self.faculty2 = Faculty.objects.create(school=self.school2, name="Faculty of Humanities", code="FOH")
        self.dept3 = Department.objects.create(faculty=self.faculty2, name="English", code="ENG")

        # Create students in each department
        self.s1_user = User.objects.create_user(identifier="STU001", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student1 = Student.objects.create(user=self.s1_user, matric_number="STU001", full_name="Student Dept1", department=self.dept1, level=100)

        self.s2_user = User.objects.create_user(identifier="STU002", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student2 = Student.objects.create(user=self.s2_user, matric_number="STU002", full_name="Student Dept2", department=self.dept2, level=200)

        self.s3_user = User.objects.create_user(identifier="STU003", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student3 = Student.objects.create(user=self.s3_user, matric_number="STU003", full_name="Student Dept3", department=self.dept3, level=300)

        # Create Admin Officers:
        # Dept Admin (Dept 1)
        self.dept_admin_user = User.objects.create_user(identifier="ADM_DEPT1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_admin_user,
            staff_id="ADM_DEPT1",
            full_name="Department Admin D1",
            level=AdminOfficer.Level.DEPARTMENT,
            scope_department=self.dept1,
        )

        # Faculty Admin (Faculty 1)
        self.fac_admin_user = User.objects.create_user(identifier="ADM_FAC1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_admin_user,
            staff_id="ADM_FAC1",
            full_name="Faculty Admin F1",
            level=AdminOfficer.Level.FACULTY,
            scope_faculty=self.faculty1,
        )

        # School Admin (School 1)
        self.sch_admin_user = User.objects.create_user(identifier="ADM_SCH1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.sch_admin = AdminOfficer.objects.create(
            user=self.sch_admin_user,
            staff_id="ADM_SCH1",
            full_name="School Admin S1",
            level=AdminOfficer.Level.SCHOOL,
            scope_school=self.school1,
        )

    def test_department_admin_scope_restrictions(self):
        self.client.force_authenticate(user=self.dept_admin_user)

        # 1. Department List: Dept Admin D1 can only see Dept 1
        url = reverse("department-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d["id"] for d in res.data]
        self.assertEqual(dept_ids, [self.dept1.id])

        # 2. Student List: Dept Admin D1 can only see Student 1
        stu_url = reverse("student-list")
        stu_res = self.client.get(stu_url)
        self.assertEqual(stu_res.status_code, status.HTTP_200_OK)
        stu_ids = [s["id"] for s in stu_res.data]
        self.assertIn(self.student1.id, stu_ids)
        self.assertNotIn(self.student2.id, stu_ids)
        self.assertNotIn(self.student3.id, stu_ids)

        # 3. Direct access to Dept 2 detail should be 404 because queryset excludes it
        detail_url = reverse("department-detail", kwargs={"pk": self.dept2.id})
        detail_res = self.client.get(detail_url)
        self.assertEqual(detail_res.status_code, status.HTTP_404_NOT_FOUND)

    def test_faculty_admin_downward_scope_resolution(self):
        self.client.force_authenticate(user=self.fac_admin_user)

        # Faculty Admin F1 should see Dept 1 and Dept 2 (both under Faculty 1), but NOT Dept 3
        url = reverse("department-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d["id"] for d in res.data]
        self.assertIn(self.dept1.id, dept_ids)
        self.assertIn(self.dept2.id, dept_ids)
        self.assertNotIn(self.dept3.id, dept_ids)

        # Students list should include Student 1 and Student 2, but NOT Student 3
        stu_url = reverse("student-list")
        stu_res = self.client.get(stu_url)
        self.assertEqual(stu_res.status_code, status.HTTP_200_OK)
        stu_ids = [s["id"] for s in stu_res.data]
        self.assertIn(self.student1.id, stu_ids)
        self.assertIn(self.student2.id, stu_ids)
        self.assertNotIn(self.student3.id, stu_ids)

    def test_school_admin_downward_scope_resolution(self):
        self.client.force_authenticate(user=self.sch_admin_user)

        # School Admin S1 should see all departments under School 1 (Dept 1 & Dept 2), but NOT Dept 3
        url = reverse("department-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        dept_ids = [d["id"] for d in res.data]
        self.assertIn(self.dept1.id, dept_ids)
        self.assertIn(self.dept2.id, dept_ids)
        self.assertNotIn(self.dept3.id, dept_ids)
