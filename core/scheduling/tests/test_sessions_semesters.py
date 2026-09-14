from datetime import date
from accounts.models import AdminOfficer, User
from hierarchy.models import School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import AcademicSession, Semester


class AcademicSessionAndSemesterTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Federal University", code="FED")
        self.other_school = School.objects.create(name="State University", code="STA")

        self.school_user = User.objects.create_user(
            identifier="ADM_SCH", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.school_admin = AdminOfficer.objects.create(
            user=self.school_user, staff_id="ADM_SCH", full_name="School Admin",
            level=AdminOfficer.Level.SCHOOL, scope_school=self.school,
        )

        self.other_school_user = User.objects.create_user(
            identifier="ADM_SCH2", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.other_school_admin = AdminOfficer.objects.create(
            user=self.other_school_user, staff_id="ADM_SCH2", full_name="Other School Admin",
            level=AdminOfficer.Level.SCHOOL, scope_school=self.other_school,
        )

    def test_school_admin_can_create_session(self):
        self.client.force_authenticate(user=self.school_user)
        response = self.client.post(
            "/api/scheduling/academic-sessions/",
            {
                "school": self.school.id,
                "label": "2026/2027",
                "start_date": "2026-09-01",
                "end_date": "2027-07-31",
                "is_current": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["label"], "2026/2027")

        # School admin cannot create session for another school
        denied = self.client.post(
            "/api/scheduling/academic-sessions/",
            {
                "school": self.other_school.id,
                "label": "2026/2027",
                "start_date": "2026-09-01",
                "end_date": "2027-07-31",
                "is_current": True,
            },
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_school_admin_can_create_and_activate_semester(self):
        self.client.force_authenticate(user=self.school_user)

        session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )

        # Create First Semester
        sem1_res = self.client.post(
            "/api/scheduling/semesters/",
            {
                "session": session.id,
                "name": "first",
                "start_date": "2026-09-15",
                "end_date": "2027-02-15",
                "duration_type": "weeks",
                "duration_value": 15,
                "lecture_start_date": "2026-09-20",
                "lecture_end_date": "2027-01-20",
                "exam_start_date": "2027-01-25",
                "exam_end_date": "2027-02-10",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(sem1_res.status_code, status.HTTP_201_CREATED)
        sem1_id = sem1_res.data["id"]

        # Create Second Semester
        sem2_res = self.client.post(
            "/api/scheduling/semesters/",
            {
                "session": session.id,
                "name": "second",
                "start_date": "2027-03-01",
                "end_date": "2027-07-15",
                "duration_type": "fixed",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(sem2_res.status_code, status.HTTP_201_CREATED)
        sem2_id = sem2_res.data["id"]

        # Activate Second Semester -> First Semester becomes inactive
        activate_res = self.client.post(f"/api/scheduling/semesters/{sem2_id}/activate/")
        self.assertEqual(activate_res.status_code, status.HTTP_200_OK)
        self.assertTrue(activate_res.data["is_active"])

        sem1 = Semester.objects.get(id=sem1_id)
        sem2 = Semester.objects.get(id=sem2_id)
        self.assertFalse(sem1.is_active)
        self.assertTrue(sem2.is_active)

