"""
Tests for the "managers manage managers" RBAC model.

Hierarchy in tests:
    School 1 → Faculty 1 → Dept 1 (CSC), Dept 2 (MTH)
    School 2 → Faculty 2 → Dept 3 (ENG)

Admin ladder:
    sch1_admin  (school,  School 1)
    fac1_admin  (faculty, Faculty 1 under School 1)
    fac2_admin  (faculty, Faculty 2 under School 2)
    dept1_admin (department, Dept 1 under Fac 1)
    dept2_admin (department, Dept 2 under Fac 1)
    dept3_admin (department, Dept 3 under Fac 2)

Rules being enforced:
  - School Admin   → sees Faculty-scoped admins in their school ONLY
  - Faculty Admin  → sees Department-scoped admins in their faculty ONLY
  - Dept Admin     → sees students & lecturers in their dept ONLY
  - Higher tiers   → get empty list for students / lecturers endpoints
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, LecturerStaff, Student, User
from hierarchy.models import Department, Faculty, School


class ScopedRBACPermissionsTests(APITestCase):
    def setUp(self):
        # ── Hierarchy ──────────────────────────────────────────────────────
        self.school1 = School.objects.create(name="School of Science", code="SOS")
        self.fac1 = Faculty.objects.create(school=self.school1, name="Faculty of Physical Sciences", code="FPS")
        self.dept1 = Department.objects.create(faculty=self.fac1, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.fac1, name="Mathematics", code="MTH")

        self.school2 = School.objects.create(name="School of Arts", code="SOA")
        self.fac2 = Faculty.objects.create(school=self.school2, name="Faculty of Humanities", code="FOH")
        self.dept3 = Department.objects.create(faculty=self.fac2, name="English", code="ENG")

        # ── Admin Officers ─────────────────────────────────────────────────
        self.sch1_user = User.objects.create_user(
            identifier="SCH_ADM1", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.sch1_admin = AdminOfficer.objects.create(
            user=self.sch1_user, staff_id="SCH_ADM1", full_name="School Admin 1",
            level=AdminOfficer.Level.SCHOOL, scope_school=self.school1,
        )

        self.fac1_user = User.objects.create_user(
            identifier="FAC_ADM1", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.fac1_admin = AdminOfficer.objects.create(
            user=self.fac1_user, staff_id="FAC_ADM1", full_name="Faculty Admin 1",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.fac1,
        )

        self.fac2_user = User.objects.create_user(
            identifier="FAC_ADM2", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.fac2_admin = AdminOfficer.objects.create(
            user=self.fac2_user, staff_id="FAC_ADM2", full_name="Faculty Admin 2",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.fac2,
        )

        self.dept1_user = User.objects.create_user(
            identifier="DEPT_ADM1", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.dept1_admin = AdminOfficer.objects.create(
            user=self.dept1_user, staff_id="DEPT_ADM1", full_name="Dept Admin 1",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1,
        )

        self.dept2_user = User.objects.create_user(
            identifier="DEPT_ADM2", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.dept2_admin = AdminOfficer.objects.create(
            user=self.dept2_user, staff_id="DEPT_ADM2", full_name="Dept Admin 2",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept2,
        )

        self.dept3_user = User.objects.create_user(
            identifier="DEPT_ADM3", password="password",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.dept3_admin = AdminOfficer.objects.create(
            user=self.dept3_user, staff_id="DEPT_ADM3", full_name="Dept Admin 3",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept3,
        )

        # ── Students & Lecturers ───────────────────────────────────────────
        self.s1_user = User.objects.create_user(
            identifier="STU1", password="password",
            role=User.Role.STUDENT, requires_password_reset=False,
        )
        self.student1 = Student.objects.create(
            user=self.s1_user, matric_number="STU1",
            full_name="Student 1", department=self.dept1, level=100,
        )

        self.s3_user = User.objects.create_user(
            identifier="STU3", password="password",
            role=User.Role.STUDENT, requires_password_reset=False,
        )
        self.student3 = Student.objects.create(
            user=self.s3_user, matric_number="STU3",
            full_name="Student 3", department=self.dept3, level=100,
        )

        self.l1_user = User.objects.create_user(
            identifier="LEC1", password="password",
            role=User.Role.LECTURER, requires_password_reset=False,
        )
        self.lecturer1 = LecturerStaff.objects.create(
            user=self.l1_user, staff_id="LEC1",
            full_name="Lecturer 1", department=self.dept1,
        )

        self.l3_user = User.objects.create_user(
            identifier="LEC3", password="password",
            role=User.Role.LECTURER, requires_password_reset=False,
        )
        self.lecturer3 = LecturerStaff.objects.create(
            user=self.l3_user, staff_id="LEC3",
            full_name="Lecturer 3", department=self.dept3,
        )

    # ── Admin Officer Visibility ───────────────────────────────────────────

    def test_school_admin_sees_only_faculty_admins_in_their_school(self):
        """School Admin sees ONLY faculty-scoped admins under their school — NOT dept admins."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.get(reverse("admin-officer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in res.data]

        # Must see Faculty Admin 1 (Faculty 1 → School 1)
        self.assertIn(self.fac1_admin.id, ids)
        # Must NOT see department admins at all — those belong to faculty admins
        self.assertNotIn(self.dept1_admin.id, ids)
        self.assertNotIn(self.dept2_admin.id, ids)
        # Must NOT see self
        self.assertNotIn(self.sch1_admin.id, ids)
        # Must NOT see admins from School 2
        self.assertNotIn(self.fac2_admin.id, ids)
        self.assertNotIn(self.dept3_admin.id, ids)

    def test_school_admin_can_create_faculty_admin_in_their_school(self):
        """School Admin can create a faculty-scoped admin under their school."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "NEW_FAC", "full_name": "New Faculty Admin",
             "level": "faculty", "scope_faculty": self.fac1.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_school_admin_cannot_create_dept_admin(self):
        """School Admin cannot bypass tier — must not create a dept-scoped admin directly."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "BAD_DEPT", "full_name": "Bad Dept Admin",
             "level": "department", "scope_department": self.dept1.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("level", res.data)

    def test_school_admin_cannot_create_admin_outside_their_school(self):
        """School Admin cannot create a faculty admin under a faculty from another school."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "WRONG_SCH", "full_name": "Wrong School Fac Admin",
             "level": "faculty", "scope_faculty": self.fac2.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_faculty_admin_sees_only_dept_admins_in_their_faculty(self):
        """Faculty Admin sees ONLY department-scoped admins under their faculty."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.get(reverse("admin-officer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [a["id"] for a in res.data]

        # Must see Dept Admin 1 & 2 (both under Faculty 1)
        self.assertIn(self.dept1_admin.id, ids)
        self.assertIn(self.dept2_admin.id, ids)
        # Must NOT see self, school admin, or any admin from Faculty 2
        self.assertNotIn(self.fac1_admin.id, ids)
        self.assertNotIn(self.sch1_admin.id, ids)
        self.assertNotIn(self.fac2_admin.id, ids)
        self.assertNotIn(self.dept3_admin.id, ids)

    def test_faculty_admin_can_create_dept_admin_in_their_faculty(self):
        """Faculty Admin can create a dept-scoped admin under a dept in their faculty."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "NEW_DEPT", "full_name": "New Dept Admin",
             "level": "department", "scope_department": self.dept1.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_faculty_admin_cannot_create_faculty_admin(self):
        """Faculty Admin cannot escalate — must not create a same-level admin."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "ESCALATE", "full_name": "Elevated Admin",
             "level": "faculty", "scope_faculty": self.fac1.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("level", res.data)

    def test_faculty_admin_cannot_create_admin_outside_their_faculty(self):
        """Faculty Admin cannot create a dept admin outside their faculty."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "WRONG_FAC", "full_name": "Wrong Dept Admin",
             "level": "department", "scope_department": self.dept3.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dept_admin_sees_no_admin_officers(self):
        """Department Admin gets an empty list from the admin-officer endpoint."""
        self.client.force_authenticate(user=self.dept1_user)
        res = self.client.get(reverse("admin-officer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_dept_admin_cannot_create_any_admin_officer(self):
        """Department Admin gets HTTP 400 attempting to create any admin officer."""
        self.client.force_authenticate(user=self.dept1_user)
        res = self.client.post(
            reverse("admin-officer-list"),
            {"staff_id": "ROGUE", "full_name": "Rogue Admin",
             "level": "department", "scope_department": self.dept1.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", res.data)

    # ── Student / Lecturer Visibility ──────────────────────────────────────

    def test_dept_admin_sees_only_students_in_their_dept(self):
        """Department Admin sees students from their department only."""
        self.client.force_authenticate(user=self.dept1_user)
        res = self.client.get(reverse("student-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [s["id"] for s in res.data]
        self.assertIn(self.student1.id, ids)
        self.assertNotIn(self.student3.id, ids)

    def test_dept_admin_sees_only_lecturers_in_their_dept(self):
        """Department Admin sees lecturers from their department only."""
        self.client.force_authenticate(user=self.dept1_user)
        res = self.client.get(reverse("lecturer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [l["id"] for l in res.data]
        self.assertIn(self.lecturer1.id, ids)
        self.assertNotIn(self.lecturer3.id, ids)

    def test_faculty_admin_sees_no_students(self):
        """Faculty Admin gets empty list from students endpoint — not their concern."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.get(reverse("student-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_faculty_admin_sees_no_lecturers(self):
        """Faculty Admin gets empty list from lecturers endpoint."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.get(reverse("lecturer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_school_admin_sees_no_students(self):
        """School Admin gets empty list from students endpoint."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.get(reverse("student-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_school_admin_sees_no_lecturers(self):
        """School Admin gets empty list from lecturers endpoint."""
        self.client.force_authenticate(user=self.sch1_user)
        res = self.client.get(reverse("lecturer-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    def test_dept_admin_cannot_view_student_in_another_dept(self):
        """Department Admin gets 404 attempting to access a student from another dept."""
        self.client.force_authenticate(user=self.dept1_user)
        url = reverse("student-detail", kwargs={"pk": self.student3.id})
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_dept_admin_cannot_edit_student_in_another_dept(self):
        """Department Admin gets 404 on PATCH for a student outside their scope."""
        self.client.force_authenticate(user=self.dept1_user)
        url = reverse("student-detail", kwargs={"pk": self.student3.id})
        res = self.client.patch(url, {"full_name": "Hacked Name"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_dept_admin_cannot_create_student_in_another_dept(self):
        """Department Admin gets HTTP 400 attempting to enroll a student in another dept."""
        self.client.force_authenticate(user=self.dept1_user)
        res = self.client.post(
            reverse("student-list"),
            {"matric_number": "BAD001", "full_name": "Bad Student",
             "department": self.dept3.id, "level": 100},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("department", res.data)

    def test_faculty_admin_cannot_create_student(self):
        """Faculty Admin cannot create any student (not their tier)."""
        self.client.force_authenticate(user=self.fac1_user)
        res = self.client.post(
            reverse("student-list"),
            {"matric_number": "FAC001", "full_name": "Fac Student",
             "department": self.dept1.id, "level": 100},
            format="json",
        )
        # Student creation by a faculty admin goes through student viewset,
        # which returns an empty queryset for them — serializer validation blocks the scope.
        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])
