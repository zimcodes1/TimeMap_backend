import datetime
from accounts.models import AdminOfficer, Student, User
from courses.models import Course, CourseRegistration
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import ExamSitting, LectureSession, TimetableEntry
from venues.models import Venue


class SchedulingTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Uni", code="U1")
        self.faculty = Faculty.objects.create(school=self.school, name="Fac", code="F1")
        self.dept = Department.objects.create(faculty=self.faculty, name="CS", code="C1")

        self.admin_user = User.objects.create_user(identifier="ADM_SCHED", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM_SCHED", full_name="Admin Sched", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept)

        self.student_user = User.objects.create_user(identifier="STU_SCHED", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student = Student.objects.create(user=self.student_user, matric_number="STU_SCHED", full_name="Student Sched", department=self.dept, level=100)

        self.venue = Venue.objects.create(
            name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept
        )
        self.course = Course.objects.create(
            code="CSC201", title="Data Structures", level=200, owning_level="department", owning_department=self.dept
        )

        CourseRegistration.objects.create(student=self.student, course=self.course, academic_session="2025/2026")

    def test_recurring_lecture_materialization(self):
        self.client.force_authenticate(user=self.admin_user)
        url = "/api/scheduling/entries/"
        payload = {
            "entry_type": "lecture",
            "title": "CSC201 Lecture",
            "course": self.course.id,
            "venue": self.venue.id,
            "start_time": "09:00:00",
            "end_time": "11:00:00",
            "recurrence_rule": "weekly:tuesday",
            "recurrence_start_date": "2026-08-01",  # Saturday
            "recurrence_end_date": "2026-08-31",    # Monday
            "academic_session": "2025/2026",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        entry_id = res.data["id"]
        # In Aug 2026, Tuesdays fall on Aug 4, Aug 11, Aug 18, Aug 25 (4 sessions)
        sessions = LectureSession.objects.filter(timetable_entry_id=entry_id)
        self.assertEqual(sessions.count(), 4)

        session_dates = [s.session_date.strftime("%Y-%m-%d") for s in sessions]
        self.assertIn("2026-08-04", session_dates)
        self.assertIn("2026-08-11", session_dates)
        self.assertIn("2026-08-18", session_dates)
        self.assertIn("2026-08-25", session_dates)

    def test_exam_sitting_candidate_count_autocalculated(self):
        self.client.force_authenticate(user=self.admin_user)

        # 1. Create exam timetable entry
        entry = TimetableEntry.objects.create(
            entry_type="exam",
            title="CSC201 Exam",
            course=self.course,
            venue=self.venue,
            start_time="09:00:00",
            end_time="12:00:00",
            created_by=self.admin,
            academic_session="2025/2026",
        )

        # 2. Create exam sitting via API without candidate count provided
        url = "/api/scheduling/exam-sittings/"
        payload = {
            "timetable_entry": entry.id,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["registered_candidates_count"], 1)
