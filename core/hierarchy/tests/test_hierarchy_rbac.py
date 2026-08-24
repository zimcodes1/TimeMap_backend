"""
Tests for Hierarchy RBAC write and view permissions.

Rules:
- University Admin / Superuser: Can create/edit/delete Schools only.
- School Admin: Can create/edit/delete Faculties within their assigned school. Cannot create Schools or Departments.
- Faculty Admin: Can create/edit/delete Departments within their assigned faculty. Cannot create Schools or Faculties.
- Department Admin: Read-only access to hierarchy objects (cannot create/edit/delete anything).
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, User
from hierarchy.models import Department, Faculty, School


class HierarchyRBACPermissionsTests(APITestCase):
    def setUp(self):
        # ── Hierarchy ──────────────────────────────────────────────────────
        self.school1 = School.objects.create(name="School of Science", code="SOS")
        self.fac1 = Faculty.objects.create(school=self.school1, name="Faculty of Science", code="FOS")
        self.dept1 = Department.objects.create(faculty=self.fac1, name="Computer Science", code="CSC")

        self.school2 = School.objects.create(name="School of Arts", code="SOA")
        self.fac2 = Faculty.objects.create(school=self.school2, name="Faculty of Arts", code="FOA")
        self.dept2 = Department.objects.create(faculty=self.fac2, name="English", code="ENG")

        # ── Admins ─────────────────────────────────────────────────────────
        # 1. University Admin
        self.univ_user = User.objects.create_user(
            identifier="UNIV_ADM", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.univ_admin = AdminOfficer.objects.create(
            user=self.univ_user, staff_id="UNIV_ADM", full_name="University Admin",
            level="university",
        )

        # 2. School Admin (School 1)
        self.sch_user = User.objects.create_user(
            identifier="SCH_ADM", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.sch_admin = AdminOfficer.objects.create(
            user=self.sch_user, staff_id="SCH_ADM", full_name="School Admin",
            level="school", scope_school=self.school1,
        )

        # 3. Faculty Admin (Faculty 1)
        self.fac_user = User.objects.create_user(
            identifier="FAC_ADM", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_user, staff_id="FAC_ADM", full_name="Faculty Admin",
            level="faculty", scope_faculty=self.fac1,
        )

        # 4. Department Admin (Dept 1)
        self.dept_user = User.objects.create_user(
            identifier="DEPT_ADM", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_user, staff_id="DEPT_ADM", full_name="Dept Admin",
            level="department", scope_department=self.dept1,
        )

    # ── School Management Tests ────────────────────────────────────────────

    def test_university_admin_can_create_school(self):
        self.client.force_authenticate(user=self.univ_user)
        res = self.client.post(
            reverse("school-list"),
            {"name": "School of Medicine", "code": "SOM"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_university_admin_cannot_create_faculty(self):
        self.client.force_authenticate(user=self.univ_user)
        res = self.client.post(
            reverse("faculty-list"),
            {"school": self.school1.id, "name": "Faculty of Law", "code": "FOL"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_university_admin_cannot_create_department(self):
        self.client.force_authenticate(user=self.univ_user)
        res = self.client.post(
            reverse("department-list"),
            {"faculty": self.fac1.id, "name": "Physics", "code": "PHY"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_school_admin_cannot_create_school(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.post(
            reverse("school-list"),
            {"name": "Unauthorized School", "code": "UNAUTH"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_school_admin_can_create_faculty_in_assigned_school(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.post(
            reverse("faculty-list"),
            {"school": self.school1.id, "name": "Faculty of Tech", "code": "FOT"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_school_admin_cannot_create_faculty_in_another_school(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.post(
            reverse("faculty-list"),
            {"school": self.school2.id, "name": "Bad Faculty", "code": "BADF"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_school_admin_cannot_create_department(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.post(
            reverse("department-list"),
            {"faculty": self.fac1.id, "name": "Physics", "code": "PHY"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── Faculty Management Tests ───────────────────────────────────────────

    def test_faculty_admin_cannot_create_school(self):
        self.client.force_authenticate(user=self.fac_user)
        res = self.client.post(
            reverse("school-list"),
            {"name": "Bad School", "code": "BADS"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_admin_cannot_create_faculty(self):
        self.client.force_authenticate(user=self.fac_user)
        res = self.client.post(
            reverse("faculty-list"),
            {"school": self.school1.id, "name": "Bad Fac", "code": "BFAC"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_faculty_admin_can_create_department_in_assigned_faculty(self):
        self.client.force_authenticate(user=self.fac_user)
        res = self.client.post(
            reverse("department-list"),
            {"faculty": self.fac1.id, "name": "Chemistry", "code": "CHM"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_faculty_admin_cannot_create_department_in_another_faculty(self):
        self.client.force_authenticate(user=self.fac_user)
        res = self.client.post(
            reverse("department-list"),
            {"faculty": self.fac2.id, "name": "Bad Dept", "code": "BDPT"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Department Admin Read-Only Tests ───────────────────────────────────

    def test_dept_admin_cannot_create_anything(self):
        self.client.force_authenticate(user=self.dept_user)

        res_sch = self.client.post(
            reverse("school-list"),
            {"name": "Dpt School", "code": "DPTS"},
            format="json",
        )
        self.assertEqual(res_sch.status_code, status.HTTP_403_FORBIDDEN)

        res_fac = self.client.post(
            reverse("faculty-list"),
            {"school": self.school1.id, "name": "Dpt Fac", "code": "DPTF"},
            format="json",
        )
        self.assertEqual(res_fac.status_code, status.HTTP_403_FORBIDDEN)

        res_dept = self.client.post(
            reverse("department-list"),
            {"faculty": self.fac1.id, "name": "Dpt Dept", "code": "DPTD"},
            format="json",
        )
        self.assertEqual(res_dept.status_code, status.HTTP_403_FORBIDDEN)
