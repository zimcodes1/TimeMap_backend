import datetime
from accounts.models import AdminOfficer, Student, User
from courses.models import Course
from discrepancies.models import DiscrepancyRequest
from hierarchy.models import Department, Faculty, School
from reporting.models import ClassRepReport
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import LectureSession, TimetableEntry
from venues.models import Venue


class AnalyticsWorkflowTests(APITestCase):
    def setUp(self):
        # Setup hierarchy
        self.school = School.objects.create(name="Federal Uni", code="FUN")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")

        # Admin
        self.admin_user = User.objects.create_user(identifier="ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM1", full_name="Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept)

        # Student & Class Rep
        self.rep_user = User.objects.create_user(identifier="REP1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.rep_student = Student.objects.create(user=self.rep_user, matric_number="REP1", full_name="Rep Alice", department=self.dept, level=300, is_class_rep=True)

        # Venue & Course
        self.venue = Venue.objects.create(name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept)
        self.course = Course.objects.create(code="CSC301", title="Data Struct", level=300, owning_level="department", owning_department=self.dept)

        # Timetable Entry & Sessions
        today = datetime.date.today()
        self.entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC301 Lecture",
            course=self.course,
            venue=self.venue,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.admin,
            academic_session="2025/2026",
        )
        self.s1 = LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=today,
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue,
        )
        self.s2 = LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=today - datetime.timedelta(days=1),
            session_start_time=datetime.time(14, 0),
            session_end_time=datetime.time(16, 0),
            venue=self.venue,
        )

        # Seed reports
        from django.utils import timezone
        ClassRepReport.objects.create(lecture_session=self.s1, reported_by=self.rep_student, held=True, reason="OK", window_expires_at=timezone.now())
        ClassRepReport.objects.create(lecture_session=self.s2, reported_by=self.rep_student, held=False, reason="Lecturer absent", window_expires_at=timezone.now())

    def test_lecture_hold_rate_analytics(self):
        self.client.force_authenticate(user=self.admin_user)
        url = "/api/reporting/analytics/lecture-hold-rate/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        summary = res.data["summary"]
        self.assertEqual(summary["total_reports"], 2)
        self.assertEqual(summary["held_count"], 1)
        self.assertEqual(summary["not_held_count"], 1)
        self.assertEqual(summary["hold_rate_percentage"], 50.0)

    def test_venue_utilization_analytics(self):
        self.client.force_authenticate(user=self.admin_user)
        url = "/api/reporting/analytics/venue-utilization/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        summary = res.data["summary"]
        self.assertEqual(summary["total_venues"], 1)
        self.assertEqual(summary["total_booked_hours"], 4.0)

    def test_discrepancy_frequency_analytics(self):
        # Create a discrepancy request
        DiscrepancyRequest.objects.create(
            timetable_entry=self.entry,
            request_type="cancel",
            reason="Renovation",
            initiated_by=self.admin_user,
            status=DiscrepancyRequest.Status.PENDING,
        )

        self.client.force_authenticate(user=self.admin_user)
        url = "/api/reporting/analytics/discrepancy-frequency/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        summary = res.data["summary"]
        self.assertEqual(summary["total_discrepancies"], 1)

    def test_scope_isolation_for_analytics(self):
        # Non-admin student forbidden
        self.client.force_authenticate(user=self.rep_user)
        url = "/api/reporting/analytics/lecture-hold-rate/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
