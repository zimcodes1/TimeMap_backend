import datetime
from accounts.models import AdminOfficer, User
from courses.models import Course
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import LectureSession, TimetableEntry
from venues.models import Venue

from discrepancies.models import AuditLog, DiscrepancyRequest


class DiscrepancyWorkflowTests(APITestCase):
    def setUp(self):
        # Create hierarchy
        self.school = School.objects.create(name="State University", code="SU")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept1 = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.faculty, name="Physics", code="PHY")

        # Admins
        self.dept1_admin_user = User.objects.create_user(identifier="DEPT1_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept1_admin = AdminOfficer.objects.create(
            user=self.dept1_admin_user, staff_id="DEPT1_ADM", full_name="Dept1 Admin", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1
        )

        self.fac_admin_user = User.objects.create_user(identifier="FAC_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_admin_user, staff_id="FAC_ADM", full_name="Faculty Admin", level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty
        )

        # Venues
        self.venue1 = Venue.objects.create(name="CSC Hall", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept1)
        self.venue2 = Venue.objects.create(name="PHY Hall", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept2)
        self.fac_venue = Venue.objects.create(name="Faculty Aud", venue_type="lecture_hall", capacity=500, owning_level="faculty", owning_faculty=self.faculty)

        # Course
        self.course = Course.objects.create(code="CSC201", title="Prog II", level=200, owning_level="department", owning_department=self.dept1)

        # Timetable Entry & Lecture Session
        self.entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC201 Lecture",
            course=self.course,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            recurrence_rule="weekly:monday",
            recurrence_start_date=datetime.date(2026, 9, 7),
            recurrence_end_date=datetime.date(2026, 9, 28),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        self.session = LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=datetime.date(2026, 9, 14),
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue1,
        )

    def test_invalid_submission_rejection(self):
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        # Both timetable_entry and lecture_session provided
        payload_both = {
            "timetable_entry": self.entry.id,
            "lecture_session": self.session.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Testing invalid submission",
        }
        res1 = self.client.post(url, payload_both, format="json")
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # shift_venue without proposed_venue
        payload_no_venue = {
            "lecture_session": self.session.id,
            "request_type": "shift_venue",
            "reason": "Missing venue",
        }
        res2 = self.client.post(url, payload_no_venue, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instance_vs_pattern_discrepancy_lifecycle(self):
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        # Submit instance-level shift_venue request for single session
        payload = {
            "lecture_session": self.session.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Maintenance in CSC Hall for Sept 14",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        discrepancy_id = res.data["id"]

        # Approve discrepancy request
        approve_url = f"/api/discrepancies/requests/{discrepancy_id}/approve/"
        res_app = self.client.post(approve_url)
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)
        self.assertEqual(res_app.data["status"], DiscrepancyRequest.Status.APPLIED)

        # Verify target session updated to venue2 and status shifted
        self.session.refresh_from_db()
        self.assertEqual(self.session.venue_id, self.venue2.id)
        self.assertEqual(self.session.status, LectureSession.Status.SHIFTED)

        # Verify parent timetable entry venue remains venue1 (pattern untouched!)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.venue_id, self.venue1.id)

    def test_submission_conflict_revalidation(self):
        self.client.force_authenticate(user=self.dept1_admin_user)

        # Existing session in venue1 on Sept 14 (10:00 - 12:00)
        entry2 = TimetableEntry.objects.create(
            entry_type="lecture",
            title="PHY Lecture",
            venue=self.venue1,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        LectureSession.objects.create(
            timetable_entry=entry2,
            session_date=datetime.date(2026, 9, 14),
            session_start_time=datetime.time(10, 0),
            session_end_time=datetime.time(12, 0),
            venue=self.venue1,
        )

        # Attempt to shift another session to venue1 on Sept 14 (10:00 - 11:30) -> Overlaps on same-level venue!
        url = "/api/discrepancies/requests/"
        payload = {
            "lecture_session": self.session.id,
            "request_type": "shift_time",
            "proposed_start_time": "10:00:00",
            "proposed_end_time": "11:30:00",
            "reason": "Shift time overlapping existing session",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("conflicts", res.data)

    def test_withdraw_discrepancy_request(self):
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        payload = {
            "lecture_session": self.session.id,
            "request_type": "cancel",
            "reason": "Change of plans",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        discrepancy_id = res.data["id"]

        withdraw_url = f"/api/discrepancies/requests/{discrepancy_id}/withdraw/"
        res_w = self.client.post(withdraw_url)
        self.assertEqual(res_w.status_code, status.HTTP_200_OK)
        self.assertEqual(res_w.data["status"], DiscrepancyRequest.Status.WITHDRAWN)

    def test_generic_audit_log_capture(self):
        self.client.force_authenticate(user=self.dept1_admin_user)

        # Create a new venue via API to trigger audit log signal
        url = "/api/venues/venues/"
        payload = {
            "name": "Audit Test Hall",
            "venue_type": "lecture_hall",
            "capacity": 80,
            "owning_level": "department",
            "owning_department": self.dept1.id,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created_venue_id = res.data["id"]

        # Check AuditLog table for entry
        logs = AuditLog.objects.filter(target_model="Venue", target_id=created_venue_id)
        self.assertTrue(logs.exists())
        log = logs.first()
        self.assertEqual(log.actor, self.dept1_admin_user)
        self.assertEqual(log.action, AuditLog.Action.CREATE)

        # Query audit log API endpoint
        audit_url = "/api/discrepancies/audit-logs/"
        res_audit = self.client.get(audit_url)
        self.assertEqual(res_audit.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_audit.data["results"] if "results" in res_audit.data else res_audit.data), 1)
