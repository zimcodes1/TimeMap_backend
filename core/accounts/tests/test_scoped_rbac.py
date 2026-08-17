from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, LecturerStaff, Student, User
from hierarchy.models import Department, Faculty, School


class ScopedRBACPermissionsTests(APITestCase):
    def setUp(self):
        # Create hierarchy structure:
        # School 1 -> Faculty 1 -> Dept 1 (CSC), Dept 2 (MTH)
        self.school1 = School.objects.create(name="School of Science", code="SOS")
        self.fac1 = Faculty.objects.create(school=self.school1, name="Faculty of Physical Sciences", code="FPS")
        self.dept1 = Department.objects.create(faculty=self.fac1, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.fac1, name="Mathematics", code="MTH")

        # School 2 -> Faculty 2 -> Dept 3 (ENG)
        self.school2 = School.objects.create(name="School of Arts", code="SOA")
        self.fac2 = Faculty.objects.create(school=self.school2, name="Faculty of Humanities", code="FOH")
        self.dept3 = Department.objects.create(faculty=self.fac2, name="English", code="ENG")

        # Create Admin Officers:
        # 1. School Admin (School 1)
        self.sch1_user = User.objects.create_user(identifier="SCH_ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.sch1_admin = AdminOfficer.objects.create(
            user=self.sch1_user, staff_id="SCH_ADM1", full_name="School Admin 1", level=AdminOfficer.Level.SCHOOL, scope_school=self.school1
        )

        # 2. Faculty Admin (Faculty 1 under School 1)
        self.fac1_user = User.objects.create_user(identifier="FAC_ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.fac1_admin = AdminOfficer.objects.create(
            user=self.fac1_user, staff_id="FAC_ADM1", full_name="Faculty Admin 1", level=AdminOfficer.Level.FACULTY, scope_faculty=self.fac1
        )

        # 3. Faculty Admin (Faculty 2 under School 2)
        self.fac2_user = User.objects.create_user(identifier="FAC_ADM2", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.fac2_admin = AdminOfficer.objects.create(
            user=self.fac2_user, staff_id="FAC_ADM2", full_name="Faculty Admin 2", level=AdminOfficer.Level.FACULTY, scope_faculty=self.fac2
        )

        # 4. Department Admin (Dept 1 under Faculty 1)
        self.dept1_user = User.objects.create_user(identifier="DEPT_ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept1_admin = AdminOfficer.objects.create(
            user=self.dept1_user, staff_id="DEPT_ADM1", full_name="Dept Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1
        )

        # 5. Department Admin (Dept 2 under Faculty 1)
        self.dept2_user = User.objects.create_user(identifier="DEPT_ADM2", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept2_admin = AdminOfficer.objects.create(
            user=self.dept2_user, staff_id="DEPT_ADM2", full_name="Dept Admin 2", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept2
        )

        # 6. Department Admin (Dept 3 under Faculty 2)
        self.dept3_user = User.objects.create_user(identifier="DEPT_ADM3", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept3_admin = AdminOfficer.objects.create(
            user=self.dept3_user, staff_id="DEPT_ADM3", full_name="Dept Admin 3", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept3
        )

        # Create Students & Lecturers
        self.s1_user = User.objects.create_user(identifier="STU1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student1 = Student.objects.create(user=self.s1_user, matric_number="STU1", full_name="Student 1", department=self.dept1, level=100)

        self.s3_user = User.objects.create_user(identifier="STU3", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student3 = Student.objects.create(user=self.s3_user, matric_number="STU3", full_name="Student 3", department=self.dept3, level=100)

    def test_department_admin_cannot_see_or_create_any_admin_officer(self):
        self.client.force_authenticate(user=self.dept1_user)

        # GET /api/auth/admins/ returns empty list for Department Admin
        url = reverse("admin-officer-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

        # POST /api/auth/admins/ fails
        create_res = self.client.post(
            url,
            {
                "staff_id": "NEW_ADM",
                "full_name": "New Admin",
                "level": "department",
                "scope_department": self.dept1.id,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", create_res.data)

    def test_faculty_admin_can_only_see_and_create_department_admins_in_their_faculty(self):
        self.client.force_authenticate(user=self.fac1_user)

        # GET /api/auth/admins/ -> Faculty Admin 1 sees Dept Admin 1 & Dept Admin 2, but NOT School Admin 1, Faculty Admin 1 (self), Faculty Admin 2, or Dept Admin 3
        url = reverse("admin-officer-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        admin_ids = [a["id"] for a in res.data]
        self.assertIn(self.dept1_admin.id, admin_ids)
        self.assertIn(self.dept2_admin.id, admin_ids)
        self.assertNotIn(self.dept3_admin.id, admin_ids)
        self.assertNotIn(self.fac1_admin.id, admin_ids)
        self.assertNotIn(self.sch1_admin.id, admin_ids)

        # Attempting to create a Faculty Admin should fail
        fail_res = self.client.post(
            url,
            {
                "staff_id": "NEW_FAC_ADM",
                "full_name": "New Fac Admin",
                "level": "faculty",
                "scope_faculty": self.fac1.id,
            },
            format="json",
        )
        self.assertEqual(fail_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("level", fail_res.data)

        # Creating a Department Admin in Dept 1 should succeed
        ok_res = self.client.post(
            url,
            {
                "staff_id": "NEW_DEPT_ADM",
                "full_name": "New Dept Admin",
                "level": "department",
                "scope_department": self.dept1.id,
            },
            format="json",
        )
        self.assertEqual(ok_res.status_code, status.HTTP_201_CREATED)

    def test_school_admin_can_only_see_faculty_and_dept_admins_in_their_school(self):
        self.client.force_authenticate(user=self.sch1_user)

        url = reverse("admin-officer-list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        admin_ids = [a["id"] for a in res.data]
        # Should see Faculty Admin 1, Dept Admin 1, Dept Admin 2
        self.assertIn(self.fac1_admin.id, admin_ids)
        self.assertIn(self.dept1_admin.id, admin_ids)
        self.assertIn(self.dept2_admin.id, admin_ids)
        # Should NOT see self (School Admin 1), Faculty Admin 2 (School 2), or Dept Admin 3 (School 2)
        self.assertNotIn(self.sch1_admin.id, admin_ids)
        self.assertNotIn(self.fac2_admin.id, admin_ids)
        self.assertNotIn(self.dept3_admin.id, admin_ids)

    def test_admin_cannot_create_student_outside_their_scope(self):
        # Dept Admin 1 attempts to create student in Dept 3 (School 2)
        self.client.force_authenticate(user=self.dept1_user)
        stu_url = reverse("student-list")
        res = self.client.post(
            stu_url,
            {
                "matric_number": "BAD_STU01",
                "full_name": "Bad Student",
                "department": self.dept3.id,
                "level": 100,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", res.data)

    def test_department_admin_cannot_see_or_edit_student_in_another_department(self):
        self.client.force_authenticate(user=self.dept1_user)

        # GET /api/auth/students/ -> Dept Admin 1 sees student1 (Dept 1), but NOT student3 (Dept 3)
        stu_list_url = reverse("student-list")
        res = self.client.get(stu_list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        student_ids = [s["id"] for s in res.data]
        self.assertIn(self.student1.id, student_ids)
        self.assertNotIn(self.student3.id, student_ids)

        # Attempting to edit student3 (Dept 3) returns 404
        stu_detail_url = reverse("student-detail", kwargs={"pk": self.student3.id})
        patch_res = self.client.patch(stu_detail_url, {"full_name": "Hacked Name"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_404_NOT_FOUND)
