from datetime import date
from accounts.models import AdminOfficer, LecturerStaff, User
from courses.models import Course
from hierarchy.models import Department, Faculty, Program, School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import (
    AcademicSession,
    GenerationScopePermission,
    LectureSession,
    Semester,
    TimetableEntry,
    TimetableGenerationRun,
)
from student_counts.models import ProgramStudentCount
from venues.models import Venue


class GenerationAPITests(APITestCase):
    def setUp(self):
        # 1. Hierarchy
        self.school = School.objects.create(name="School of Computing", code="SOC")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FOS")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        self.program = Program.objects.create(department=self.dept, name="B.Sc Computer Science", code="CSC", max_level=400)

        # 2. Users
        self.superuser = User.objects.create_superuser(
            identifier="SYS_ADMIN", password="password", requires_password_reset=False
        )

        self.school_user = User.objects.create_user(
            identifier="SCH_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.school_admin = AdminOfficer.objects.create(
            user=self.school_user, staff_id="SCH01", full_name="School Admin",
            level=AdminOfficer.Level.SCHOOL, scope_school=self.school,
        )

        self.fac_user = User.objects.create_user(
            identifier="FAC_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_user, staff_id="FAC01", full_name="Faculty Admin",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty,
        )

        # 3. Session & Semester
        self.session = AcademicSession.objects.create(
            school=self.school, label="2026/2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31), is_current=True,
        )
        self.semester = Semester.objects.create(
            session=self.session, name="first",
            start_date=date(2026, 9, 15), end_date=date(2027, 2, 15),
            lecture_start_date=date(2026, 9, 20), lecture_end_date=date(2026, 10, 20),  # 1 month lecture period
            is_active=True,
        )

        # 4. Venues
        self.hall = Venue.objects.create(
            name="Hall 1", venue_type="lecture_hall", capacity=100,
            owning_level="school", owning_school=self.school,
        )
        self.lab = Venue.objects.create(
            name="Computer Lab 1", venue_type="laboratory", capacity=50,
            owning_level="department", owning_department=self.dept,
        )

        # 5. Lecturer
        self.lec_user = User.objects.create_user(
            identifier="LEC01", password="password", role=User.Role.LECTURER, requires_password_reset=False
        )
        self.lecturer = LecturerStaff.objects.create(
            user=self.lec_user, staff_id="LEC01", full_name="Dr. Smith", department=self.dept
        )

        # 6. Courses
        self.course1 = Course.objects.create(
            code="CSC101", title="Introduction to CS", level=100,
            course_type="lecture", required_occurrences_per_week=2,
            owning_level="department", owning_department=self.dept,
            semester=self.semester,
        )
        self.course1.lecturers.add(self.lecturer)

        self.course2 = Course.objects.create(
            code="CSC102", title="Computing Practical", level=100,
            course_type="practical", required_occurrences_per_week=1,
            owning_level="department", owning_department=self.dept,
            semester=self.semester,
        )
        self.course2.lecturers.add(self.lecturer)

        # Student headcounts
        ProgramStudentCount.objects.create(program=self.program, level=100, count=45)

    def test_school_admin_can_generate_school_timetable(self):
        self.client.force_authenticate(user=self.school_user)

        payload = {
            "semester_id": self.semester.id,
            "scope_type": "school",
            "scope_id": self.school.id,
            "population_size": 20,
            "max_generations": 30,
        }

        res = self.client.post("/api/scheduling/generate/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("status", res.data)
        self.assertIn("conflict_report", res.data)
        self.assertIn("assignments_payload", res.data)
        self.assertEqual(res.data["hard_conflicts_count"], 0)

        run_id = res.data["id"]

        # Practical course must be assigned to laboratory
        assignments = res.data["assignments_payload"]
        lab_assigned = any(a["course_code"] == "CSC102" and a["venue_id"] == self.lab.id for a in assignments)
        self.assertTrue(lab_assigned, "Practical course CSC102 must be scheduled in the lab.")

        # Test listing runs
        list_res = self.client.get("/api/scheduling/generate/runs/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(r["id"] == run_id for r in list_res.data))

        # Test get run detail
        detail_res = self.client.get(f"/api/scheduling/generate/runs/{run_id}/")
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data["id"], run_id)

    def test_generate_with_semester_alias(self):
        self.client.force_authenticate(user=self.school_user)
        # Verify that sending "semester" instead of "semester_id" also works
        payload = {
            "semester": self.semester.id,
            "scope_type": "school",
            "scope_id": self.school.id,
            "population_size": 20,
            "max_generations": 30,
        }
        res = self.client.post("/api/scheduling/generate/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["hard_conflicts_count"], 0)

    def test_faculty_admin_permission_control(self):
        self.client.force_authenticate(user=self.fac_user)

        payload = {
            "semester_id": self.semester.id,
            "scope_type": "faculty",
            "scope_id": self.faculty.id,
            "population_size": 20,
            "max_generations": 20,
        }

        # 1. By default, faculty generation is disabled -> 403 Forbidden
        res = self.client.post("/api/scheduling/generate/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("disabled", res.data["error"].lower())

        # 2. System Admin enables faculty generation for the school
        self.client.force_authenticate(user=self.superuser)
        perm_res = self.client.patch(
            "/api/scheduling/generate/permissions/",
            {"school": self.school.id, "allow_faculty_generation": True},
            format="json",
        )
        self.assertEqual(perm_res.status_code, status.HTTP_200_OK)
        self.assertTrue(perm_res.data["allow_faculty_generation"])

        # 3. Now faculty admin can generate for their faculty!
        self.client.force_authenticate(user=self.fac_user)
        res_allowed = self.client.post("/api/scheduling/generate/", payload, format="json")
        self.assertEqual(res_allowed.status_code, status.HTTP_200_OK)

    def test_publishing_generation_run(self):
        self.client.force_authenticate(user=self.school_user)

        payload = {
            "semester_id": self.semester.id,
            "scope_type": "school",
            "scope_id": self.school.id,
            "population_size": 20,
            "max_generations": 30,
        }

        gen_res = self.client.post("/api/scheduling/generate/", payload, format="json")
        run_id = gen_res.data["id"]

        # Verify no TimetableEntry exists yet (publish has not occurred)
        self.assertEqual(TimetableEntry.objects.filter(semester=self.semester).count(), 0)

        # Publish the run
        pub_res = self.client.post(f"/api/scheduling/generate/runs/{run_id}/publish/", format="json")
        self.assertEqual(pub_res.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_res.data["status"], "published")
        self.assertGreater(pub_res.data["published_entries_count"], 0)
        self.assertGreater(pub_res.data["materialized_sessions_count"], 0)

        # Verify TimetableEntry and LectureSession rows now exist in the database
        entries = TimetableEntry.objects.filter(semester=self.semester)
        self.assertEqual(entries.count(), pub_res.data["published_entries_count"])

        sessions = LectureSession.objects.filter(timetable_entry__semester=self.semester)
        self.assertEqual(sessions.count(), pub_res.data["materialized_sessions_count"])

        # Run record is marked published
        run = TimetableGenerationRun.objects.get(id=run_id)
        self.assertTrue(run.is_published)

