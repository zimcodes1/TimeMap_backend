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

        self.dept2_admin_user = User.objects.create_user(identifier="DEPT2_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept2_admin = AdminOfficer.objects.create(
            user=self.dept2_admin_user, staff_id="DEPT2_ADM", full_name="Dept2 Admin", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept2
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

    def test_non_admin_cannot_submit_discrepancy(self):
        student_user = User.objects.create_user(identifier="STU001", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.client.force_authenticate(user=student_user)
        url = "/api/discrepancies/requests/"

        payload = {
            "lecture_session": self.session.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Student attempting to submit discrepancy",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_submission_rejection(self):
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        # Attempting to target lecture_session is rejected
        payload_session = {
            "lecture_session": self.session.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Instance level discrepancy should be rejected",
        }
        res_session = self.client.post(url, payload_session, format="json")
        self.assertEqual(res_session.status_code, status.HTTP_400_BAD_REQUEST)

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
            "timetable_entry": self.entry.id,
            "request_type": "shift_venue",
            "reason": "Missing venue",
        }
        res2 = self.client.post(url, payload_no_venue, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instance_vs_pattern_discrepancy_lifecycle(self):
        # Dept1 admin submits request targeting venue2 (Physics venue) for pattern entry
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        payload = {
            "timetable_entry": self.entry.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Maintenance in CSC Hall for Sept 14",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        discrepancy_id = res.data["id"]
        self.assertEqual(res.data["routed_to"], self.dept2_admin.id)

        approve_url = f"/api/discrepancies/requests/{discrepancy_id}/approve/"

        # Requester (dept1_admin) cannot approve request routed to dept2_admin
        res_req_app = self.client.post(approve_url)
        self.assertEqual(res_req_app.status_code, status.HTTP_403_FORBIDDEN)

        # Overseeing Faculty Admin cannot approve request routed to dept2_admin (inspect only)
        self.client.force_authenticate(user=self.fac_admin_user)
        res_fac_app = self.client.post(approve_url)
        self.assertEqual(res_fac_app.status_code, status.HTTP_403_FORBIDDEN)

        # Dept2 Admin (the routed admin) approves request
        self.client.force_authenticate(user=self.dept2_admin_user)
        res_app = self.client.post(approve_url)
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)
        self.assertEqual(res_app.data["status"], DiscrepancyRequest.Status.APPROVED)

        # Verify timetable entry venue updated to venue2
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.venue_id, self.venue2.id)

        # Verify child session also updated
        self.session.refresh_from_db()
        self.assertEqual(self.session.venue_id, self.venue2.id)

    def test_self_service_discrepancy_approval(self):
        # Dept1 admin submits request targeting venue1 (CSC venue - own department)
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        payload = {
            "timetable_entry": self.entry.id,
            "request_type": "shift_time",
            "proposed_start_time": "12:00:00",
            "proposed_end_time": "14:00:00",
            "reason": "Shift time within own department venue",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        discrepancy_id = res.data["id"]
        # Routed to self (dept1_admin)
        self.assertEqual(res.data["routed_to"], self.dept1_admin.id)
        self.assertTrue(res.data["can_approve"])

        # Dept1 admin approves their own internal request
        approve_url = f"/api/discrepancies/requests/{discrepancy_id}/approve/"
        res_app = self.client.post(approve_url)
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)
        self.assertEqual(res_app.data["status"], DiscrepancyRequest.Status.APPROVED)

        self.entry.refresh_from_db()
        self.assertEqual(self.entry.start_time, datetime.time(12, 0))

    def test_discrepancy_approval_frees_previous_venue_time(self):
        # Verify venue1 on Sept 14 (9:00 - 11:00) has self.session currently
        from scheduling.conflict_engine import check_venue_overlap
        initial_conflicts = check_venue_overlap(
            venue=self.venue1,
            date=datetime.date(2026, 9, 14),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertTrue(len(initial_conflicts) > 0)

        # Shift pattern to venue2 via discrepancy
        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"
        payload = {
            "timetable_entry": self.entry.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Shift out to free CSC Hall",
        }
        res = self.client.post(url, payload, format="json")
        discrepancy_id = res.data["id"]

        # Dept2 Admin approves
        self.client.force_authenticate(user=self.dept2_admin_user)
        approve_url = f"/api/discrepancies/requests/{discrepancy_id}/approve/"
        res_app = self.client.post(approve_url)
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)

        # Verify venue1 on Sept 14 (9:00 - 11:00) is now completely FREE!
        freed_conflicts = check_venue_overlap(
            venue=self.venue1,
            date=datetime.date(2026, 9, 14),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(freed_conflicts, [])

        # Verify venue2 now has the clash
        new_venue_conflicts = check_venue_overlap(
            venue=self.venue2,
            date=datetime.date(2026, 9, 14),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertTrue(len(new_venue_conflicts) > 0)

    def test_submission_conflict_revalidation(self):
        self.client.force_authenticate(user=self.dept1_admin_user)

        # Existing session in venue1 on Sept 14 (10:00 - 12:00)
        entry2 = TimetableEntry.objects.create(
            entry_type="lecture",
            title="PHY Lecture",
            venue=self.venue1,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
            recurrence_rule="weekly:monday",
            recurrence_start_date=datetime.date(2026, 9, 7),
            recurrence_end_date=datetime.date(2026, 9, 28),
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

        # Attempt to shift another pattern to venue1 on Sept 14 (10:00 - 11:30) -> Overlaps on same-level venue!
        url = "/api/discrepancies/requests/"
        payload = {
            "timetable_entry": self.entry.id,
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
            "timetable_entry": self.entry.id,
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

    def test_admin_visibility_and_department_filtering(self):
        other_school = School.objects.create(name="Other University", code="OU")
        other_admin_user = User.objects.create_user(
            identifier="OTHER_ADM",
            password="password",
            role=User.Role.ADMIN,
            requires_password_reset=False,
        )
        AdminOfficer.objects.create(
            user=other_admin_user,
            staff_id="OTHER_ADM",
            full_name="Other Admin",
            level=AdminOfficer.Level.SCHOOL,
            scope_school=other_school,
        )

        self.client.force_authenticate(user=self.dept1_admin_user)
        url = "/api/discrepancies/requests/"

        payload = {
            "timetable_entry": self.entry.id,
            "request_type": "shift_venue",
            "proposed_venue": self.venue2.id,
            "reason": "Dept2 venue request should only be visible to the relevant routed admin.",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        discrepancy_id = res.data["id"]

        # Faculty admin can see requests from departments under their faculty
        self.client.force_authenticate(user=self.fac_admin_user)
        res_factory = self.client.get(url)
        self.assertEqual(res_factory.status_code, status.HTTP_200_OK)
        factory_results = res_factory.data if isinstance(res_factory.data, list) else res_factory.data.get("results", [])
        factory_ids = [item["id"] for item in factory_results]
        self.assertIn(discrepancy_id, factory_ids)

        # Faculty admin filtering by department
        res_dept_filter = self.client.get(f"{url}?department={self.dept1.id}")
        self.assertEqual(res_dept_filter.status_code, status.HTTP_200_OK)
        dept_results = res_dept_filter.data if isinstance(res_dept_filter.data, list) else res_dept_filter.data.get("results", [])
        dept_ids = [item["id"] for item in dept_results]
        self.assertIn(discrepancy_id, dept_ids)

        # Other school admin cannot see this discrepancy
        self.client.force_authenticate(user=other_admin_user)
        res_other = self.client.get(url)
        self.assertEqual(res_other.status_code, status.HTTP_200_OK)
        other_results = res_other.data if isinstance(res_other.data, list) else res_other.data.get("results", [])
        other_ids = [item["id"] for item in other_results]
        self.assertNotIn(discrepancy_id, other_ids)

        # Department 1 admin can see it because initiated by them
        self.client.force_authenticate(user=self.dept1_admin_user)
        res_own = self.client.get(url)
        self.assertEqual(res_own.status_code, status.HTTP_200_OK)
        own_results = res_own.data if isinstance(res_own.data, list) else res_own.data.get("results", [])
        own_ids = [item["id"] for item in own_results]
        self.assertIn(discrepancy_id, own_ids)

    def test_direct_instance_shift_jurisdiction_and_clash_prevention(self):
        # Create a faculty-level shared course so both dept1_admin and dept2_admin can see it
        fac_course = Course.objects.create(
            code="FAC101",
            title="General Faculty Course",
            owning_level="faculty",
            owning_faculty=self.faculty,
            level=100,
        )
        fac_entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="FAC101 Lecture",
            course=fac_course,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        fac_session = LectureSession.objects.create(
            timetable_entry=fac_entry,
            session_date=datetime.date(2026, 9, 14),
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue1,
        )

        # 1. Non-creator admin (dept2_admin) attempts to shift fac_session -> 403 Forbidden
        self.client.force_authenticate(user=self.dept2_admin_user)
        url = f"/api/scheduling/sessions/{fac_session.id}/"
        payload = {
            "session_start_time": "14:00:00",
            "session_end_time": "16:00:00",
        }
        res_unauthorized = self.client.patch(url, payload, format="json")
        self.assertEqual(res_unauthorized.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Existing session in venue1 on Sept 14 (14:00 - 16:00)
        LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=datetime.date(2026, 9, 14),
            session_start_time=datetime.time(14, 0),
            session_end_time=datetime.time(16, 0),
            venue=self.venue1,
        )

        # 3. Creator admin (dept1_admin) shifts fac_session into conflicting time (14:00-16:00) -> 400 Bad Request
        self.client.force_authenticate(user=self.dept1_admin_user)
        res_clash = self.client.patch(url, payload, format="json")
        self.assertEqual(res_clash.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("conflicts", res_clash.data)

        # 4. Creator admin shifts fac_session into a FREE time (16:00-18:00) -> 200 OK, immediately in effect
        payload_ok = {
            "session_start_time": "16:00:00",
            "session_end_time": "18:00:00",
        }
        res_ok = self.client.patch(url, payload_ok, format="json")
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ok.data["status"], "shifted")
        self.assertEqual(res_ok.data["session_start_time"], "16:00:00")

        fac_session.refresh_from_db()
        self.assertEqual(fac_session.status, LectureSession.Status.SHIFTED)
        self.assertEqual(fac_session.session_start_time, datetime.time(16, 0))

    def test_hold_rate_analytics_counts_unreported_sessions_and_supports_group_by(self):
        from reporting.analytics import get_lecture_hold_rate_analytics
        data = get_lecture_hold_rate_analytics(user=self.dept1_admin_user, group_by="week")
        self.assertIn("summary", data)
        self.assertIn("unreported_count", data["summary"])
        self.assertIn("breakdown", data)

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
