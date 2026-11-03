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
                "lecture_start_date": "2027-03-05",
                "lecture_end_date": "2027-06-30",
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

    def test_semester_mutual_exclusivity_on_creation(self):
        self.client.force_authenticate(user=self.school_user)

        session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )

        # Sem 1 created as active
        s1 = Semester.objects.create(
            session=session,
            name="first",
            start_date=date(2026, 9, 15),
            end_date=date(2027, 2, 15),
            lecture_start_date=date(2026, 9, 20),
            lecture_end_date=date(2027, 1, 20),
            is_active=True,
        )
        self.assertTrue(s1.is_active)

        # Sem 2 created as active via API -> s1 must automatically become inactive
        sem2_res = self.client.post(
            "/api/scheduling/semesters/",
            {
                "session": session.id,
                "name": "second",
                "start_date": "2027-03-01",
                "end_date": "2027-07-15",
                "lecture_start_date": "2027-03-05",
                "lecture_end_date": "2027-06-30",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(sem2_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(sem2_res.data["is_active"])

        s1.refresh_from_db()
        self.assertFalse(s1.is_active)

    def test_past_semester_cannot_be_activated(self):
        self.client.force_authenticate(user=self.school_user)

        past_session = AcademicSession.objects.create(
            school=self.school,
            label="2020/2021",
            start_date=date(2020, 9, 1),
            end_date=date(2021, 7, 31),
            is_current=False,
        )

        past_sem = Semester.objects.create(
            session=past_session,
            name="first",
            start_date=date(2020, 9, 15),
            end_date=date(2021, 2, 15),
            lecture_start_date=date(2020, 9, 20),
            lecture_end_date=date(2021, 1, 20),
            is_active=False,
        )

        self.assertTrue(past_sem.is_past)
        self.assertFalse(past_sem.can_activate)

        # Attempt to activate via API should fail with 400
        res = self.client.post(f"/api/scheduling/semesters/{past_sem.id}/activate/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already passed", res.data.get("error", ""))

        # Attempt to set past session as current should fail with 400
        res_sess = self.client.post(f"/api/scheduling/academic-sessions/{past_session.id}/set-current/")
        self.assertEqual(res_sess.status_code, status.HTTP_400_BAD_REQUEST)

    def test_auto_activation_based_on_current_date(self):
        from django.utils import timezone
        from scheduling.services import sync_school_semesters

        self.client.force_authenticate(user=self.school_user)
        today = timezone.localdate()

        session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=today - timezone.timedelta(days=60),
            end_date=today + timezone.timedelta(days=200),
            is_current=True,
        )

        # Sem 1 covers today, initially inactive
        sem1 = Semester.objects.create(
            session=session,
            name="first",
            start_date=today - timezone.timedelta(days=30),
            end_date=today + timezone.timedelta(days=30),
            lecture_start_date=today - timezone.timedelta(days=25),
            lecture_end_date=today + timezone.timedelta(days=25),
            is_active=False,
        )

        # Sem 2 in the future, initially inactive
        sem2 = Semester.objects.create(
            session=session,
            name="second",
            start_date=today + timezone.timedelta(days=40),
            end_date=today + timezone.timedelta(days=120),
            lecture_start_date=today + timezone.timedelta(days=45),
            lecture_end_date=today + timezone.timedelta(days=110),
            is_active=False,
        )

        # 1. When no semester is active, sync auto-activates sem1 because today falls in its timeframe
        sync_school_semesters(school=self.school)

        sem1.refresh_from_db()
        sem2.refresh_from_db()

        self.assertTrue(sem1.is_active)
        self.assertFalse(sem2.is_active)

        # 2. When an admin explicitly activates sem2 via API, it must persist and NOT be reverted by sync
        activate_res = self.client.post(f"/api/scheduling/semesters/{sem2.id}/activate/")
        self.assertEqual(activate_res.status_code, status.HTTP_200_OK)

        sem1.refresh_from_db()
        sem2.refresh_from_db()
        self.assertFalse(sem1.is_active)
        self.assertTrue(sem2.is_active)

        # Repeated sync calls must respect the admin's manual activation
        sync_school_semesters(school=self.school)
        sem1.refresh_from_db()
        sem2.refresh_from_db()
        self.assertFalse(sem1.is_active)
        self.assertTrue(sem2.is_active)


