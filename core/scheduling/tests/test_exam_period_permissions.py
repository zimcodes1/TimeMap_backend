from datetime import date, time
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import AdminOfficer, User
from courses.models import Course
from hierarchy.models import Department, Faculty, Program, School
from venues.models import Venue
from scheduling.models import (
    AcademicSession,
    Semester,
    GenerationScopePermission,
    FacultyExamPeriod,
    TimetableEntry,
    LectureSession,
    ExamSitting,
)


class ExamPeriodPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # School, Faculty, Dept, Program
        self.school = School.objects.create(name="School of Science", code="SOS")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Natural Sciences", code="FNAS")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.program = Program.objects.create(department=self.dept, name="B.Sc Computer Science", code="CS")

        # Users: School Admin and Faculty Admin
        self.school_user = User.objects.create_user(
            identifier="SCH_ADMIN_01",
            role=User.Role.ADMIN,
            is_active=True,
            password="password123",
            requires_password_reset=False,
        )
        self.school_admin = AdminOfficer.objects.create(
            user=self.school_user,
            staff_id="STF_SCH_01",
            full_name="School Admin",
            level=AdminOfficer.Level.SCHOOL,
            scope_school=self.school,
        )

        self.fac_user = User.objects.create_user(
            identifier="FAC_ADMIN_01",
            role=User.Role.ADMIN,
            is_active=True,
            password="password123",
            requires_password_reset=False,
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_user,
            staff_id="STF_FAC_01",
            full_name="Faculty Admin",
            level=AdminOfficer.Level.FACULTY,
            scope_faculty=self.faculty,
        )

        # Academic Session & Semester with mandatory lecture dates
        self.session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )
        self.semester = Semester.objects.create(
            session=self.session,
            name=Semester.SemesterName.FIRST,
            start_date=date(2026, 9, 15),
            end_date=date(2027, 2, 15),
            lecture_start_date=date(2026, 9, 20),
            lecture_end_date=date(2027, 1, 20),
            is_active=True,
        )

        self.venue = Venue.objects.create(
            name="Exam Hall A",
            capacity=200,
            owning_school=self.school,
            owning_level=Venue.OwningLevel.SCHOOL,
            venue_type=Venue.VenueType.EXAM_HALL,
        )

        self.course = Course.objects.create(
            code="CSC201",
            title="Data Structures",
            level=200,
            owning_department=self.dept,
        )

    def test_exam_cannot_be_scheduled_without_exam_period(self):
        """Scheduling an exam entry must fail if no exam period is defined for the scope."""
        self.client.force_authenticate(user=self.school_user)
        res = self.client.post(
            "/api/scheduling/entries/",
            {
                "entry_type": "exam",
                "title": "CSC201 Final Exam",
                "course": self.course.id,
                "venue": self.venue.id,
                "start_time": "08:00:00",
                "end_time": "10:00:00",
                "recurrence_start_date": "2027-01-25",
                "semester": self.semester.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("examination period has not been defined", str(res.data))

    def test_school_admin_can_set_exam_period_and_schedule_exam(self):
        """School Admin can set the school-wide exam period and then schedule exams."""
        self.client.force_authenticate(user=self.school_user)
        set_res = self.client.post(
            f"/api/scheduling/semesters/{self.semester.id}/set-exam-period/",
            {
                "exam_start_date": "2027-01-22",
                "exam_end_date": "2027-02-10",
            },
            format="json",
        )
        self.assertEqual(set_res.status_code, status.HTTP_200_OK)

        # Now scheduling exam inside exam period succeeds
        res = self.client.post(
            "/api/scheduling/entries/",
            {
                "entry_type": "exam",
                "title": "CSC201 Final Exam",
                "course": self.course.id,
                "venue": self.venue.id,
                "start_time": "08:00:00",
                "end_time": "10:00:00",
                "recurrence_start_date": "2027-01-25",
                "semester": self.semester.id,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Verify automatic session and sitting creation
        entry_id = res.data["id"]
        self.assertTrue(LectureSession.objects.filter(timetable_entry_id=entry_id, session_date="2027-01-25").exists())
        self.assertTrue(ExamSitting.objects.filter(timetable_entry_id=entry_id).exists())

    def test_faculty_admin_exam_period_permission_flow(self):
        """Faculty Admin cannot customize exam period until allowed, and revoking clears it."""
        # 1. Faculty Admin is blocked initially
        self.client.force_authenticate(user=self.fac_user)
        blocked_res = self.client.post(
            f"/api/scheduling/semesters/{self.semester.id}/faculty-exam-periods/",
            {
                "faculty": self.faculty.id,
                "start_date": "2027-01-25",
                "end_date": "2027-02-05",
            },
            format="json",
        )
        self.assertEqual(blocked_res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. School Admin enables allow_faculty_exam_period
        self.client.force_authenticate(user=self.school_user)
        perm_res = self.client.patch(
            "/api/scheduling/generate/permissions/",
            {
                "school": self.school.id,
                "allow_faculty_exam_period": True,
            },
            format="json",
        )
        self.assertEqual(perm_res.status_code, status.HTTP_200_OK)
        self.assertTrue(perm_res.data["allow_faculty_exam_period"])

        # 3. Faculty Admin can now set custom faculty exam period
        self.client.force_authenticate(user=self.fac_user)
        custom_res = self.client.post(
            f"/api/scheduling/semesters/{self.semester.id}/faculty-exam-periods/",
            {
                "faculty": self.faculty.id,
                "start_date": "2027-01-25",
                "end_date": "2027-02-05",
            },
            format="json",
        )
        self.assertEqual(custom_res.status_code, status.HTTP_200_OK)
        self.assertTrue(FacultyExamPeriod.objects.filter(semester=self.semester, faculty=self.faculty).exists())

        # 4. School Admin revokes permission -> custom faculty period is overwritten/deleted
        self.client.force_authenticate(user=self.school_user)
        revoke_res = self.client.patch(
            "/api/scheduling/generate/permissions/",
            {
                "school": self.school.id,
                "allow_faculty_exam_period": False,
            },
            format="json",
        )
        self.assertEqual(revoke_res.status_code, status.HTTP_200_OK)
        self.assertFalse(FacultyExamPeriod.objects.filter(semester=self.semester, faculty=self.faculty).exists())
