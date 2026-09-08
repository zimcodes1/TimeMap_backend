from accounts.models import AdminOfficer, User
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase

from student_counts.models import DepartmentStudentCount


class DepartmentStudentCountTests(APITestCase):
    def setUp(self):
        school = School.objects.create(name="Science", code="SCI")
        self.faculty = Faculty.objects.create(school=school, name="Computing", code="CMP")
        self.department = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.other_department = Department.objects.create(faculty=self.faculty, name="Mathematics", code="MTH")
        self.department_user = User.objects.create_user(
            identifier="DEPT", password="password", role="admin", requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.department_user, staff_id="DEPT", full_name="Department Admin",
            level="department", scope_department=self.department,
        )
        self.faculty_user = User.objects.create_user(
            identifier="FAC", password="password", role="admin", requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.faculty_user, staff_id="FAC", full_name="Faculty Admin",
            level="faculty", scope_faculty=self.faculty,
        )

    def test_department_admin_can_create_only_own_total(self):
        self.client.force_authenticate(self.department_user)
        response = self.client.post("/api/student-counts/departments/", {"department": self.department.id, "level": 200, "count": 240}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 240)
        self.assertEqual(response.data["updated_by_name"], "Department Admin")

        analytics = self.client.get("/api/student-counts/departments/analytics/")
        self.assertEqual(analytics.status_code, status.HTTP_200_OK)
        self.assertEqual(analytics.data["available_dimensions"], ["level"])
        self.assertEqual(analytics.data["by_department"], [])
        self.assertEqual(analytics.data["summary"]["levels_reporting"], 1)

        denied = self.client.post("/api/student-counts/departments/", {"department": self.other_department.id, "level": 200, "count": 99}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_higher_admin_can_view_scope_but_not_write(self):
        DepartmentStudentCount.objects.create(department=self.department, level=200, count=240)
        DepartmentStudentCount.objects.create(department=self.other_department, level=200, count=180)
        self.client.force_authenticate(self.faculty_user)
        response = self.client.get("/api/student-counts/departments/analytics/?faculty_id=%s" % self.faculty.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["total_students"], 420)
        self.assertEqual(len(response.data["by_department"]), 2)
        self.assertEqual(response.data["by_faculty"], [])
        self.assertNotIn("school", response.data["available_dimensions"])

        denied = self.client.patch("/api/student-counts/departments/1/", {"count": 1}, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
