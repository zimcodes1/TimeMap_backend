import datetime
from accounts.models import AdminOfficer, Student, User
from courses.models import Course
from discrepancies.models import DiscrepancyRequest
from discrepancies.services import approve_discrepancy_request
from hierarchy.models import Department, Faculty, School
from notifications.models import DeviceToken, Notification
from notifications.services import (
    dispatch_event_notification,
    register_device_token,
    send_fcm_push_notification,
)
from reporting.services import run_unreported_sessions_sweep
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import LectureSession, TimetableEntry
from venues.models import Venue


class NotificationsWorkflowTests(APITestCase):
    def setUp(self):
        # Create hierarchy & users
        self.school = School.objects.create(name="Federal Uni", code="FUN")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")

        self.user = User.objects.create_user(identifier="USER1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student = Student.objects.create(user=self.user, matric_number="USER1", full_name="User 1", department=self.dept, level=100)

        self.admin_user = User.objects.create_user(identifier="ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM1", full_name="Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept)

        self.venue = Venue.objects.create(name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept)

    def test_device_token_registration_and_deactivation(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/notifications/devices/"
        payload = {
            "fcm_token": "sample_fcm_token_12345",
            "platform": "android",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["is_active"])

        # Deactivate token
        deact_url = "/api/notifications/devices/deactivate/"
        res_d = self.client.post(deact_url, {"fcm_token": "sample_fcm_token_12345"}, format="json")
        self.assertEqual(res_d.status_code, status.HTTP_200_OK)

        token = DeviceToken.objects.get(fcm_token="sample_fcm_token_12345")
        self.assertFalse(token.is_active)

    def test_inbox_notifications_read_status_and_unread_count(self):
        self.client.force_authenticate(user=self.user)

        # Create two notifications
        n1 = dispatch_event_notification(recipient=self.user, notification_type="session_shifted", title="Session Shifted", body="Your lecture has moved.")
        n2 = dispatch_event_notification(recipient=self.user, notification_type="discrepancy_approved", title="Request Approved", body="Your request was approved.")

        # Check unread count
        count_url = "/api/notifications/inbox/unread-count/"
        res_c = self.client.get(count_url)
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)
        self.assertEqual(res_c.data["unread_count"], 2)

        # Mark n1 as read
        read_url = f"/api/notifications/inbox/{n1.id}/read/"
        res_r = self.client.post(read_url)
        self.assertEqual(res_r.status_code, status.HTTP_200_OK)
        self.assertTrue(res_r.data["is_read"])

        # Mark all read
        mark_url = "/api/notifications/inbox/mark-all-read/"
        res_m = self.client.post(mark_url)
        self.assertEqual(res_m.status_code, status.HTTP_200_OK)

        res_c2 = self.client.get(count_url)
        self.assertEqual(res_c2.data["unread_count"], 0)

    def test_discrepancy_approval_triggers_notification_pipeline(self):
        # Create pending discrepancy request
        entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC101 Lecture",
            venue=self.venue,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.admin,
            academic_session="2025/2026",
        )
        discrepancy = DiscrepancyRequest.objects.create(
            timetable_entry=entry,
            request_type="cancel",
            reason="Holiday",
            initiated_by=self.user,
            status=DiscrepancyRequest.Status.PENDING,
        )

        # Register device token for user
        register_device_token(user=self.user, fcm_token="valid_fcm_token_99", platform="ios")

        # Admin approves discrepancy
        approve_discrepancy_request(discrepancy=discrepancy, admin_user=self.admin_user)

        # Verify Notification row was created for self.user
        notifs = Notification.objects.filter(recipient=self.user, notification_type=Notification.NotificationType.DISCREPANCY_APPROVED)
        self.assertTrue(notifs.exists())
        self.assertEqual(notifs.first().related_id, discrepancy.id)

    def test_dead_fcm_token_deactivation_during_push(self):
        # Register a token starting with 'invalid_'
        token = register_device_token(user=self.user, fcm_token="invalid_dead_token_555", platform="android")
        self.assertTrue(token.is_active)

        notification = Notification.objects.create(
            recipient=self.user,
            notification_type="session_cancelled",
            title="Test",
            body="Test Body",
        )

        # Trigger push dispatch
        send_fcm_push_notification(notification)

        # Verify token was deactivated
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_unreported_sessions_sweep_triggers_notifications(self):
        # Create an expired session (3 days ago)
        past_date = datetime.date.today() - datetime.timedelta(days=3)
        course = Course.objects.create(code="CSC101", title="Intro to CS", level=100, owning_level="department", owning_department=self.dept)
        entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC101 Lecture",
            course=course,
            venue=self.venue,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.admin,
            academic_session="2025/2026",
        )
        session = LectureSession.objects.create(
            timetable_entry=entry,
            session_date=past_date,
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue,
        )

        # Run sweep
        flagged_count = run_unreported_sessions_sweep(window_hours=2)
        self.assertGreaterEqual(flagged_count, 1)

        # Verify admin received notification
        notifs = Notification.objects.filter(recipient=self.admin_user, notification_type=Notification.NotificationType.SESSION_UNREPORTED)
        self.assertTrue(notifs.exists())
