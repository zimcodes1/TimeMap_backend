import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student, User
from courses.models import Course
from django.utils import timezone
from hierarchy.models import Department, Faculty, School
from reporting.models import ClassRepReport, UnreportedSessionFlag
from reporting.services import run_unreported_sessions_sweep
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import LectureSession, TimetableEntry
from venues.models import Venue


class ReportingWorkflowTests(APITestCase):
    def setUp(self):
        # Create hierarchy
        self.school = School.objects.create(name="Federal Uni", code="FUN")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.other_dept = Department.objects.create(faculty=self.faculty, name="Physics", code="PHY")

        # Admin
        self.admin_user = User.objects.create_user(identifier="ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM1", full_name="Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept)

        # Lecturer
        self.lecturer_user = User.objects.create_user(identifier="LEC1", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        self.lecturer = LecturerStaff.objects.create(user=self.lecturer_user, staff_id="LEC1", full_name="Dr. Smith", department=self.dept)

        # Class Rep Student
        self.rep_user = User.objects.create_user(identifier="REP1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.rep_student = Student.objects.create(user=self.rep_user, matric_number="REP1", full_name="Rep Alice", department=self.dept, level=300, is_class_rep=True)

        # Regular Student (Non Rep)
        self.regular_user = User.objects.create_user(identifier="STU1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.regular_student = Student.objects.create(user=self.regular_user, matric_number="STU1", full_name="Bob", department=self.dept, level=300, is_class_rep=False)

        # Venue & Course
        self.venue = Venue.objects.create(name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept)
        self.course = Course.objects.create(code="CSC301", title="Data Struct", level=300, owning_level="department", owning_department=self.dept)
        self.course.lecturers.add(self.lecturer)

        # Recent Session (Today)
        today = timezone.now().date()
        now_time = timezone.now().time()
        start_time = (datetime.datetime.now() - datetime.timedelta(hours=1)).time()
        end_time = datetime.datetime.now().time()

        self.entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC301 Lecture",
            course=self.course,
            venue=self.venue,
            start_time=start_time,
            end_time=end_time,
            created_by=self.admin,
            academic_session="2025/2026",
        )
        self.recent_session = LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=today,
            session_start_time=start_time,
            session_end_time=end_time,
            venue=self.venue,
        )

        # Expired Session (3 Days Ago)
        past_date = today - datetime.timedelta(days=3)
        self.expired_session = LectureSession.objects.create(
            timetable_entry=self.entry,
            session_date=past_date,
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue,
        )

    def test_valid_report_submission_within_window(self):
        self.client.force_authenticate(user=self.rep_user)
        url = "/api/reporting/reports/"
        payload = {
            "lecture_session": self.recent_session.id,
            "held": True,
            "reason": "Lecture held successfully on time.",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["held"])
        self.assertEqual(res.data["reported_by_name"], "Rep Alice")

        # Verify session status updated
        self.recent_session.refresh_from_db()
        self.assertEqual(self.recent_session.status, LectureSession.Status.HELD)

    def test_window_expired_report_rejection(self):
        self.client.force_authenticate(user=self.rep_user)
        url = "/api/reporting/reports/"
        payload = {
            "lecture_session": self.expired_session.id,
            "held": False,
            "reason": "Late report attempt.",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", str(res.data))

    def test_non_rep_or_wrong_department_rejection(self):
        # Non-rep student attempt
        self.client.force_authenticate(user=self.regular_user)
        url = "/api/reporting/reports/"
        payload = {
            "lecture_session": self.recent_session.id,
            "held": True,
            "reason": "Regular student trying to report.",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unreported_sessions_sweep_and_admin_acknowledgement(self):
        # Trigger sweep
        flagged_count = run_unreported_sessions_sweep(window_hours=2)
        self.assertGreaterEqual(flagged_count, 1)

        # Check flag table
        flags = UnreportedSessionFlag.objects.filter(lecture_session=self.expired_session)
        self.assertTrue(flags.exists())
        flag = flags.first()

        # Admin acknowledges flag
        self.client.force_authenticate(user=self.admin_user)
        ack_url = f"/api/reporting/flags/{flag.id}/acknowledge/"
        res_ack = self.client.post(ack_url)
        self.assertEqual(res_ack.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ack.data["acknowledged_by_name"], "Admin 1")

    def test_lecturer_dispute_response(self):
        # Class rep files report
        report = ClassRepReport.objects.create(
            lecture_session=self.recent_session,
            reported_by=self.rep_student,
            held=False,
            reason="Lecturer did not show up.",
            window_expires_at=timezone.now() + datetime.timedelta(hours=2),
        )

        # Assigned lecturer responds
        self.client.force_authenticate(user=self.lecturer_user)
        resp_url = f"/api/reporting/reports/{report.id}/respond/"
        payload = {"response_text": "I was present, class rep arrived late."}
        res = self.client.post(resp_url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        report.refresh_from_db()
        self.assertEqual(report.lecturer_response, "I was present, class rep arrived late.")
        self.assertIsNotNone(report.lecturer_responded_at)
