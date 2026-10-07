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

    def test_venue_availability_filtering_by_timeslot(self):
        import datetime
        from scheduling.models import AcademicSession, Semester, TimetableEntry

        session = AcademicSession.objects.create(school=self.school, label="2025/2026", start_date=datetime.date(2025, 9, 1), end_date=datetime.date(2026, 7, 1))
        sem = Semester.objects.create(
            session=session,
            name=Semester.SemesterName.FIRST,
            start_date=datetime.date(2025, 9, 1),
            end_date=datetime.date(2026, 1, 31),
            lecture_start_date=datetime.date(2025, 9, 8),
            lecture_end_date=datetime.date(2025, 12, 19),
        )

        venue_free = Venue.objects.create(name="Free Room", venue_type="lecture_hall", capacity=50, owning_level="department", owning_department=self.dept)
        venue_booked = Venue.objects.create(name="Booked Room", venue_type="lecture_hall", capacity=50, owning_level="department", owning_department=self.dept)

        # Create a booking for venue_booked on Monday 08:00 - 10:00
        TimetableEntry.objects.create(
            semester=sem,
            venue=venue_booked,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO",
            status=TimetableEntry.Status.PUBLISHED,
        )

        self.client.force_authenticate(user=self.dept_admin_user)

        # Query without timeslot: both venues returned
        res_all = self.client.get("/api/venues/venues/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        all_ids = [v["id"] for v in res_all.data]
        self.assertIn(venue_free.id, all_ids)
        self.assertIn(venue_booked.id, all_ids)

        # Query with Monday 08:00 - 10:00: venue_booked must be excluded
        res_avail = self.client.get("/api/venues/venues/?day_of_week=Monday&start_time=08:00:00&end_time=10:00:00&available_only=true")
        self.assertEqual(res_avail.status_code, status.HTTP_200_OK)
        avail_ids = [v["id"] for v in res_avail.data]
        self.assertIn(venue_free.id, avail_ids)
        self.assertNotIn(venue_booked.id, avail_ids)

    def test_friday_jummat_exclusion(self):
        Venue.objects.create(name="Hall A", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept)
        self.client.force_authenticate(user=self.dept_admin_user)

        # Friday 12:00 - 14:00 is Jummat prayer break: strictly returns no venues
        res = self.client.get("/api/venues/venues/?day_of_week=Friday&start_time=12:00:00&end_time=14:00:00&available_only=true")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)
