from datetime import date
from accounts.models import AdminOfficer, LecturerStaff, User
from courses.models import Course
from hierarchy.models import Department, Faculty, Program, School
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from scheduling.models import (
    AcademicSession,
    Semester,
    TimetableGenerationRun,
)
from scheduling.optimizer.decomposed_generator import generate_school_timetable_decomposed
from student_counts.models import ProgramStudentCount
from venues.models import Venue


class DecomposedGeneratorTests(APITransactionTestCase):
    def setUp(self):
        # School
        self.school = School.objects.create(name="University of Science", code="UOS")

        # Two faculties: Faculty A (larger pop: 500) and Faculty B (smaller pop: 200)
        self.fac_b = Faculty.objects.create(school=self.school, name="Faculty Beta", code="FB")
        self.dept_b = Department.objects.create(faculty=self.fac_b, name="Dept B", code="DB")
        self.prog_b = Program.objects.create(department=self.dept_b, name="Prog B", code="PB", max_level=400)
        ProgramStudentCount.objects.create(program=self.prog_b, level=100, count=200)

        self.fac_a = Faculty.objects.create(school=self.school, name="Faculty Alpha", code="FA")
        self.dept_a = Department.objects.create(faculty=self.fac_a, name="Dept A", code="DA")
        self.prog_a = Program.objects.create(department=self.dept_a, name="Prog A", code="PA", max_level=400)
        ProgramStudentCount.objects.create(program=self.prog_a, level=100, count=500)

        # Venues
        self.venue_a = Venue.objects.create(
            name="Hall A", code="HA", capacity=300, is_active=True,
            owning_level="faculty", owning_faculty=self.fac_a
        )
        self.venue_b = Venue.objects.create(
            name="Hall B", code="HB", capacity=300, is_active=True,
            owning_level="faculty", owning_faculty=self.fac_b
        )

        # Session & Semester
        self.session = AcademicSession.objects.create(
            school=self.school, label="2026/2027",
            start_date=date(2026, 10, 1), end_date=date(2027, 7, 31),
            is_current=True
        )
        self.semester = Semester.objects.create(
            session=self.session, name="first", is_active=True,
            start_date=date(2026, 11, 1), end_date=date(2027, 2, 28),
            lecture_start_date=date(2026, 11, 1), lecture_end_date=date(2027, 2, 28),
        )

        # Courses
        self.course_a = Course.objects.create(
            code="CRA101", title="Course Alpha 1", level=100, semester=self.semester,
            owning_level="faculty", owning_faculty=self.fac_a,
            required_occurrences_per_week=2, program_scope="program", target_program=self.prog_a
        )
        self.course_b = Course.objects.create(
            code="CRB101", title="Course Beta 1", level=100, semester=self.semester,
            owning_level="faculty", owning_faculty=self.fac_b,
            required_occurrences_per_week=2, program_scope="program", target_program=self.prog_b
        )

        # User
        self.superuser = User.objects.create_superuser(
            identifier="DECOMPOSED_ADMIN", password="password", requires_password_reset=False
        )

    def test_faculty_population_ordering_and_generation(self):
        progress_events = []

        def callback(evt):
            progress_events.append(evt)

        run = generate_school_timetable_decomposed(
            semester=self.semester,
            school_id=self.school.id,
            progress_callback=callback,
            initiated_by=self.superuser,
        )

        self.assertIsNotNone(run)
        self.assertEqual(run.scope_type, TimetableGenerationRun.ScopeType.SCHOOL)
        self.assertEqual(run.status, TimetableGenerationRun.Status.COMPLETED)
        self.assertTrue(len(run.assignments_payload) >= 4)  # 2 occ for Course A + 2 occ for Course B

        # Verify progress events were emitted
        self.assertTrue(len(progress_events) >= 3)

        # Verify ordering: Faculty Alpha (pop: 500) must appear before Faculty Beta (pop: 200)
        faculty_events = [e for e in progress_events if e.get("stage") == "faculty" and e.get("status") == "running"]
        self.assertTrue(len(faculty_events) >= 2)
        self.assertEqual(faculty_events[0]["facultyCode"], "FA")  # Alpha first (500 pop)
        self.assertEqual(faculty_events[1]["facultyCode"], "FB")  # Beta second (200 pop)

    def test_streaming_endpoint(self):
        self.client.force_authenticate(user=self.superuser)
        payload = {
            "semester_id": self.semester.id,
            "scope_type": "school",
            "scope_id": self.school.id,
        }
        response = self.client.post("/api/scheduling/generate/stream/", data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Content-Type"), "text/event-stream")

        # Read streamed content
        content = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("data: ", content)
        self.assertIn('"stage": "complete"', content)
