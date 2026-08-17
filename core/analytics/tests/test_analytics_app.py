import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student, User
from analytics.models import AnalyticsQueryLog
from courses.models import Course
from hierarchy.models import Department, Faculty, School
from reporting.models import ClassRepReport
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import LectureSession, TimetableEntry
from venues.models import Venue


class RoleBasedAnalyticsTests(APITestCase):
    def setUp(self):
        # Create hierarchy
        self.school = School.objects.create(name="Federal Uni", code="FUN")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")

        # Admin
        self.admin_user = User.objects.create_user(identifier="ADM1", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.admin = AdminOfficer.objects.create(user=self.admin_user, staff_id="ADM1", full_name="Admin 1", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept)

        # Lecturer 1
        self.lecturer_user = User.objects.create_user(identifier="LEC1", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        self.lecturer = LecturerStaff.objects.create(user=self.lecturer_user, staff_id="LEC1", full_name="Dr. Smith", department=self.dept)

        # Lecturer 2 (Other)
        self.other_lecturer_user = User.objects.create_user(identifier="LEC2", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        self.other_lecturer = LecturerStaff.objects.create(user=self.other_lecturer_user, staff_id="LEC2", full_name="Dr. Jones", department=self.dept)

        # Class Rep Student
        self.rep_user = User.objects.create_user(identifier="REP1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.rep_student = Student.objects.create(user=self.rep_user, matric_number="REP1", full_name="Rep Alice", department=self.dept, level=300, is_class_rep=True)

        # Regular Student (Non-Rep)
        self.regular_user = User.objects.create_user(identifier="STU1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.regular_student = Student.objects.create(user=self.regular_user, matric_number="STU1", full_name="Bob", department=self.dept, level=300, is_class_rep=False)

        # Venue & Courses
        self.venue = Venue.objects.create(name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept)
        self.course1 = Course.objects.create(code="CSC301", title="Data Struct", level=300, owning_level="department", owning_department=self.dept)
        self.course1.lecturers.add(self.lecturer)

        self.course2 = Course.objects.create(code="CSC303", title="Algorithms", level=300, owning_level="department", owning_department=self.dept)
        self.course2.lecturers.add(self.other_lecturer)

        # Timetable Entries & Sessions
        today = datetime.date.today()
        self.entry1 = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC301 Lecture",
            course=self.course1,
            venue=self.venue,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.admin,
            academic_session="2025/2026",
        )
        self.session1 = LectureSession.objects.create(
            timetable_entry=self.entry1,
            session_date=today,
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue,
            status=LectureSession.Status.HELD,
        )

        self.entry2 = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC303 Lecture",
            course=self.course2,
            venue=self.venue,
            start_time=datetime.time(11, 0),
            end_time=datetime.time(13, 0),
            created_by=self.admin,
            academic_session="2025/2026",
        )
        self.session2 = LectureSession.objects.create(
            timetable_entry=self.entry2,
            session_date=today,
            session_start_time=datetime.time(11, 0),
            session_end_time=datetime.time(13, 0),
            venue=self.venue,
            status=LectureSession.Status.NOT_HELD,
        )

    def test_class_rep_analytics_valid_query(self):
        self.client.force_authenticate(user=self.rep_user)
        url = "/api/analytics/class-rep/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["summary"]["total_sessions"], 2)
        self.assertEqual(res.data["summary"]["held_count"], 1)
        self.assertEqual(res.data["summary"]["not_held_count"], 1)

        # Check audit log
        self.assertTrue(AnalyticsQueryLog.objects.filter(user=self.rep_user, query_type="class_rep").exists())

    def test_non_class_rep_student_forbidden(self):
        self.client.force_authenticate(user=self.regular_user)
        url = "/api/analytics/class-rep/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_lecturer_analytics_overall_and_course_filtered(self):
        self.client.force_authenticate(user=self.lecturer_user)
        url = "/api/analytics/lecturer/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["summary"]["total_sessions"], 1)
        self.assertEqual(res.data["summary"]["held_count"], 1)

        # Filter by course ID
        url_c = f"/api/analytics/lecturer/?course_id={self.course1.id}"
        res_c = self.client.get(url_c)
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)
        self.assertEqual(res_c.data["query_range"]["filtered_course"], "CSC301")

    def test_lecturer_unassigned_course_rejection(self):
        self.client.force_authenticate(user=self.lecturer_user)
        # Attempt to query course2 assigned to other lecturer
        url = f"/api/analytics/lecturer/?course_id={self.course2.id}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_analytics_per_lecturer_and_per_course(self):
        self.client.force_authenticate(user=self.admin_user)
        url = f"/api/analytics/admin/?lecturer_id={self.lecturer.id}"
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["query_range"]["filtered_lecturer"], "Dr. Smith")
        self.assertEqual(res.data["summary"]["total_sessions"], 1)
        self.assertEqual(res.data["summary"]["held_count"], 1)

        # Query per course
        url_c = f"/api/analytics/admin/?course_id={self.course2.id}"
        res_c = self.client.get(url_c)
        self.assertEqual(res_c.status_code, status.HTTP_200_OK)
        self.assertEqual(res_c.data["query_range"]["filtered_course"], "CSC303")
        self.assertEqual(res_c.data["summary"]["total_sessions"], 1)
        self.assertEqual(res_c.data["summary"]["not_held_count"], 1)
