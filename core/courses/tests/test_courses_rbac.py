"""
Tests for Courses RBAC permissions.

Rules:
- System Level (University Admin): View all courses, edit none, delete none.
- School Level Admin: View all courses, create only school level courses, no access grants.
- Faculty Level Admin: Create faculty-scope courses for their faculty, view faculty/dept/granted courses, manage grants.
- Department Scope Admin: Create/edit/delete courses in their department, grant & request access.
- Originating owner rule: Granted courses can only be edited/deleted by their originating scope admin.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, User
from courses.models import Course, CourseAccessGrant
from hierarchy.models import Department, Faculty, School


class CoursesRBACPermissionsTests(APITestCase):
    def setUp(self):
        # ── Hierarchy ──────────────────────────────────────────────────────
        self.school1 = School.objects.create(name="School of Science", code="SOS")
        self.fac1 = Faculty.objects.create(school=self.school1, name="Faculty of Science", code="FOS")
        self.dept1 = Department.objects.create(faculty=self.fac1, name="Computer Science", code="CSC")

        self.school2 = School.objects.create(name="School of Arts", code="SOA")
        self.fac2 = Faculty.objects.create(school=self.school2, name="Faculty of Arts", code="FOA")
        self.dept2 = Department.objects.create(faculty=self.fac2, name="English", code="ENG")

        # ── Admin Users ───────────────────────────────────────────────────
        # 1. University Admin
        self.univ_user = User.objects.create_user(
            identifier="UNIV_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.univ_admin = AdminOfficer.objects.create(
            user=self.univ_user, staff_id="UNIV_ADM", full_name="University Admin", level="university"
        )

        # 2. School Admin (School 1)
        self.sch_user = User.objects.create_user(
            identifier="SCH_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.sch_admin = AdminOfficer.objects.create(
            user=self.sch_user, staff_id="SCH_ADM", full_name="School Admin", level="school", scope_school=self.school1
        )

        # 3. Faculty Admin (Faculty 1)
        self.fac_user = User.objects.create_user(
            identifier="FAC_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_user, staff_id="FAC_ADM", full_name="Faculty Admin", level="faculty", scope_faculty=self.fac1
        )

        # 4. Department Admin (Dept 1)
        self.dept1_user = User.objects.create_user(
            identifier="DEPT1_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.dept1_admin = AdminOfficer.objects.create(
            user=self.dept1_user, staff_id="DEPT1_ADM", full_name="Dept 1 Admin", level="department", scope_department=self.dept1
        )

        # 5. Department Admin (Dept 2)
        self.dept2_user = User.objects.create_user(
            identifier="DEPT2_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.dept2_admin = AdminOfficer.objects.create(
            user=self.dept2_user, staff_id="DEPT2_ADM", full_name="Dept 2 Admin", level="department", scope_department=self.dept2
        )

        # ── Courses ───────────────────────────────────────────────────────
        self.sch_course = Course.objects.create(
            code="SCH101", title="General Science", level=100, owning_level="school", owning_school=self.school1
        )
        self.fac_course = Course.objects.create(
            code="FAC101", title="Faculty Science", level=100, owning_level="faculty", owning_faculty=self.fac1
        )
        self.dept1_course = Course.objects.create(
            code="CSC101", title="Intro to Programming", level=100, owning_level="department", owning_department=self.dept1
        )
        self.dept2_course = Course.objects.create(
            code="ENG101", title="Use of English", level=100, owning_level="department", owning_department=self.dept2
        )

    # ── System Level Tests ───────────────────────────────────────────────────

    def test_university_admin_can_view_all_courses(self):
        self.client.force_authenticate(user=self.univ_user)
        res = self.client.get(reverse("course-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 4)

    def test_university_admin_cannot_edit_or_delete_courses(self):
        self.client.force_authenticate(user=self.univ_user)
        url = reverse("course-detail", kwargs={"pk": self.dept1_course.id})

        patch_res = self.client.patch(url, {"title": "Hacked Title"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)

        del_res = self.client.delete(url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)

    # ── School Level Tests ───────────────────────────────────────────────────

    def test_school_admin_can_view_all_courses(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.get(reverse("course-list"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 4)

    def test_school_admin_can_create_only_school_level_course(self):
        self.client.force_authenticate(user=self.sch_user)

        # Creating school-level course in assigned school -> 201 Created
        ok_res = self.client.post(
            reverse("course-list"),
            {"code": "SCH201", "title": "Advanced Science", "level": 200, "owning_level": "school", "owning_school": self.school1.id},
            format="json",
        )
        self.assertEqual(ok_res.status_code, status.HTTP_201_CREATED)

        # Attempting to create department or faculty course -> 400 Bad Request
        fail_res = self.client.post(
            reverse("course-list"),
            {"code": "DEPT201", "title": "Dept Course", "level": 200, "owning_level": "department", "owning_department": self.dept1.id},
            format="json",
        )
        self.assertEqual(fail_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_school_admin_cannot_use_access_grants(self):
        self.client.force_authenticate(user=self.sch_user)
        res = self.client.get(reverse("course-access-grant-list"))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # ── Department Admin & Originating Owner Tests ─────────────────────────

    def test_dept_admin_can_manage_own_course_only(self):
        self.client.force_authenticate(user=self.dept1_user)

        # Edit own department course -> 200 OK
        own_url = reverse("course-detail", kwargs={"pk": self.dept1_course.id})
        ok_res = self.client.patch(own_url, {"title": "Updated Programming"}, format="json")
        self.assertEqual(ok_res.status_code, status.HTTP_200_OK)

        # Edit another department course -> 403 Forbidden or 404 Not Found (out of queryset)
        other_url = reverse("course-detail", kwargs={"pk": self.dept2_course.id})
        fail_res = self.client.patch(other_url, {"title": "Hacked English"}, format="json")
        self.assertIn(fail_res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_originating_owner_rule_for_granted_courses(self):
        """Dept 1 grants course to Dept 2. Dept 2 can view it, but CANNOT edit or delete it."""
        # Dept 1 grants CSC101 to Dept 2
        grant = CourseAccessGrant.objects.create(
            course=self.dept1_course,
            granted_to_level="department",
            granted_to_department=self.dept2,
            direction="offered",
            status="approved",
            initiated_by=self.dept1_admin,
        )

        # Dept 2 admin views course list -> CSC101 is included
        self.client.force_authenticate(user=self.dept2_user)
        list_res = self.client.get(reverse("course-list"))
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        c_ids = [c["id"] for c in list_res.data]
        self.assertIn(self.dept1_course.id, c_ids)

        # Dept 2 admin attempts to edit granted CSC101 -> 403 Forbidden
        edit_url = reverse("course-detail", kwargs={"pk": self.dept1_course.id})
        edit_res = self.client.patch(edit_url, {"title": "Dept 2 Edit Attempt"}, format="json")
        self.assertEqual(edit_res.status_code, status.HTTP_403_FORBIDDEN)

        # Dept 2 admin attempts to delete granted CSC101 -> 403 Forbidden
        del_res = self.client.delete(edit_url)
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)
