from accounts.models import AdminOfficer, User
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase
from venues.models import Facility, Venue


class VenueTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Science School", code="SCH1")
        self.faculty = Faculty.objects.create(school=self.school, name="Science Faculty", code="FAC1")
        self.dept = Department.objects.create(faculty=self.faculty, name="CS Dept", code="CS1")

        self.facility = Facility.objects.create(name="Projector")

        # Dept Admin
        self.dept_admin_user = User.objects.create_user(identifier="DEPT_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_admin_user, staff_id="DEPT_ADM", full_name="Dept Admin", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept
        )

    def test_dept_admin_create_dept_owned_venue_success(self):
        self.client.force_authenticate(user=self.dept_admin_user)
        url = "/api/venues/venues/"
        payload = {
            "name": "Lab 101",
            "venue_type": "laboratory",
            "capacity": 50,
            "facilities": [self.facility.id],
            "owning_level": "department",
            "owning_department": self.dept.id,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Venue.objects.count(), 1)

    def test_dept_admin_cannot_claim_faculty_level_ownership(self):
        self.client.force_authenticate(user=self.dept_admin_user)
        url = "/api/venues/venues/"
        payload = {
            "name": "Faculty Hall",
            "venue_type": "lecture_hall",
            "capacity": 200,
            "owning_level": "faculty",
            "owning_faculty": self.faculty.id,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", res.data)
