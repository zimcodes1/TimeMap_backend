import datetime
from accounts.models import AdminOfficer, LecturerStaff, Student, User
from courses.models import Course, CourseRegistration
from hierarchy.models import Department, Faculty, School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.conflict_engine import (
    check_interval_overlap,
    check_lecturer_clash,
    check_student_exam_clash,
    check_venue_overlap,
    determine_booking_routing,
)
from scheduling.models import ExamSitting, LectureSession, TimetableEntry
from venues.models import Venue


class ConflictEngineTests(APITestCase):
    def setUp(self):
        # Create hierarchy
        self.school = School.objects.create(name="Federal University", code="FUD")
        self.faculty1 = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.faculty2 = Faculty.objects.create(school=self.school, name="Faculty of Arts", code="FAR")

        self.dept1 = Department.objects.create(faculty=self.faculty1, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.faculty1, name="Mathematics", code="MTH")
        self.dept3 = Department.objects.create(faculty=self.faculty2, name="English", code="ENG")

        # Admins
        self.dept1_admin_user = User.objects.create_user(identifier="DEPT1_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.dept1_admin = AdminOfficer.objects.create(
            user=self.dept1_admin_user, staff_id="DEPT1_ADM", full_name="Dept1 Admin", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1
        )

        self.fac1_admin_user = User.objects.create_user(identifier="FAC1_ADM", password="password", role=User.Role.ADMIN, requires_password_reset=False)
        self.fac1_admin = AdminOfficer.objects.create(
            user=self.fac1_admin_user, staff_id="FAC1_ADM", full_name="Fac1 Admin", level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty1
        )

        # Venues
        self.venue1 = Venue.objects.create(name="LT1", venue_type="lecture_hall", capacity=100, owning_level="department", owning_department=self.dept1)
        self.venue2 = Venue.objects.create(name="Audit", venue_type="lecture_hall", capacity=300, owning_level="faculty", owning_faculty=self.faculty1)

        # Courses
        self.course1 = Course.objects.create(code="CSC101", title="CS 101", level=100, owning_level="department", owning_department=self.dept1)
        self.course2 = Course.objects.create(code="MTH101", title="Math 101", level=100, owning_level="department", owning_department=self.dept2)

        # Lecturer
        self.lecturer_user = User.objects.create_user(identifier="LEC1", password="password", role=User.Role.LECTURER, requires_password_reset=False)
        self.lecturer = LecturerStaff.objects.create(user=self.lecturer_user, staff_id="LEC1", full_name="Dr. Smith", department=self.dept1)
        self.course1.lecturers.add(self.lecturer)

        # Students
        self.student1_user = User.objects.create_user(identifier="STU1", password="password", role=User.Role.STUDENT, requires_password_reset=False)
        self.student1 = Student.objects.create(user=self.student1_user, matric_number="STU1", full_name="Alice", department=self.dept1, level=100)

        # Registrations
        CourseRegistration.objects.create(student=self.student1, course=self.course1, academic_session="2025/2026")
        CourseRegistration.objects.create(student=self.student1, course=self.course2, academic_session="2025/2026")

    def test_interval_overlap_boundary_conditions(self):
        t10 = datetime.time(10, 0)
        t11 = datetime.time(11, 0)
        t12 = datetime.time(12, 0)

        # Adjacent slots: 10:00-11:00 and 11:00-12:00 -> NO overlap
        self.assertFalse(check_interval_overlap(t10, t11, t11, t12))

        # Overlapping slots: 10:00-11:30 and 11:00-12:00 -> Overlap
        t11_30 = datetime.time(11, 30)
        self.assertTrue(check_interval_overlap(t10, t11_30, t11, t12))

    def test_venue_overlap_detection(self):
        entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC101 Lecture",
            course=self.course1,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            recurrence_rule="weekly:tuesday",
            recurrence_start_date=datetime.date(2026, 8, 1),
            recurrence_end_date=datetime.date(2026, 8, 31),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )

        # Materialize sessions (Aug 4, 11, 18, 25)
        session = LectureSession.objects.create(
            timetable_entry=entry,
            session_date=datetime.date(2026, 8, 18),  # 3 weeks in
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue1,
        )

        # Check overlapping proposal on Aug 18
        conflicts = check_venue_overlap(
            venue=self.venue1,
            date=datetime.date(2026, 8, 18),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflicting_session_id"], session.id)

    def test_student_exam_clash_detection(self):
        # Existing exam for Math 101 on Aug 20
        exam_entry1 = TimetableEntry.objects.create(
            entry_type="exam",
            title="MTH101 Exam",
            course=self.course2,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            recurrence_start_date=datetime.date(2026, 8, 20),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        ExamSitting.objects.create(timetable_entry=exam_entry1, registered_candidates_count=1)

        # Proposed exam for CS 101 on Aug 20 at overlapping time (10:00 - 13:00)
        clashes = check_student_exam_clash(
            course=self.course1,
            date=datetime.date(2026, 8, 20),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(13, 0),
            academic_session="2025/2026",
        )
        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0]["affected_student_count"], 1)
        self.assertEqual(clashes[0]["affected_students"][0]["matric_number"], "STU1")

    def test_lecturer_double_booking_detection(self):
        # Teaching session on Aug 25
        entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="CSC101 Lecture",
            course=self.course1,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        LectureSession.objects.create(
            timetable_entry=entry,
            session_date=datetime.date(2026, 8, 25),
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue1,
        )

        # Proposed invigilation or lecture at overlapping time (10:00 - 12:00)
        clashes = check_lecturer_clash(
            lecturer_ids=[self.lecturer.id],
            date=datetime.date(2026, 8, 25),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(len(clashes), 1)
        self.assertEqual(clashes[0]["lecturer_id"], self.lecturer.id)

    def test_hierarchical_routing_outcomes(self):
        # Outcome 1: PROCEED (Dept admin booking Dept1 venue with no clash)
        res1 = determine_booking_routing(
            user=self.dept1_admin_user,
            venue=self.venue1,
            date_or_start_date=datetime.date(2026, 9, 1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(res1["outcome"], "PROCEED")

        # Outcome 3: ROUTE_APPROVAL (Dept admin booking Faculty1 venue)
        res3 = determine_booking_routing(
            user=self.dept1_admin_user,
            venue=self.venue2,  # Owned at Faculty level
            date_or_start_date=datetime.date(2026, 9, 1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(res3["outcome"], "ROUTE_APPROVAL")
        self.assertEqual(res3["routed_to_admin_id"], self.fac1_admin.id)

        # Faculty Admin booking Dept1 venue (downward hierarchy resolution -> PROCEED)
        res_fac = determine_booking_routing(
            user=self.fac1_admin_user,
            venue=self.venue1,  # Dept1 venue under Faculty1
            date_or_start_date=datetime.date(2026, 9, 1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
        )
        self.assertEqual(res_fac["outcome"], "PROCEED")

    def test_api_hard_rejection_and_cross_level_routing(self):
        self.client.force_authenticate(user=self.dept1_admin_user)

        # 1. Existing session on Sept 10
        entry = TimetableEntry.objects.create(
            entry_type="lecture",
            title="Existing Lecture",
            course=self.course1,
            venue=self.venue1,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            created_by=self.dept1_admin,
            academic_session="2025/2026",
        )
        LectureSession.objects.create(
            timetable_entry=entry,
            session_date=datetime.date(2026, 9, 10),
            session_start_time=datetime.time(9, 0),
            session_end_time=datetime.time(11, 0),
            venue=self.venue1,
        )

        # Attempting clash creation -> 400 HARD_REJECT
        url = "/api/scheduling/entries/"
        payload = {
            "entry_type": "lecture",
            "title": "Clashing Lecture",
            "venue": self.venue1.id,
            "start_time": "10:00:00",
            "end_time": "12:00:00",
            "recurrence_rule": "weekly:thursday",
            "recurrence_start_date": "2026-09-10",
            "recurrence_end_date": "2026-09-30",
            "academic_session": "2025/2026",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("conflicts", res.data)

        # Cross-level booking request -> 202 ROUTE_APPROVAL
        cross_payload = {
            "entry_type": "lecture",
            "title": "Cross Level Lecture",
            "venue": self.venue2.id,  # Faculty venue
            "start_time": "14:00:00",
            "end_time": "16:00:00",
            "recurrence_rule": "weekly:thursday",
            "recurrence_start_date": "2026-09-10",
            "recurrence_end_date": "2026-09-30",
            "academic_session": "2025/2026",
        }
        res_cross = self.client.post(url, cross_payload, format="json")
        self.assertEqual(res_cross.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(res_cross.data["outcome"], "ROUTE_APPROVAL")
