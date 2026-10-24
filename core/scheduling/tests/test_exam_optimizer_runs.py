from datetime import date

from accounts.models import AdminOfficer, Student, User
from courses.models import Course, CourseRegistration
from hierarchy.models import Department, Faculty, School
from rest_framework.test import APITestCase
from scheduling.models import AcademicSession, GenerationScopePermission, Semester
from venues.models import Venue


class ExamOptimizerRunWorkflowTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Optimization School", code="OSCH")
        self.faculty = Faculty.objects.create(school=self.school, name="Science Faculty", code="OSFAC")
        self.department = Department.objects.create(faculty=self.faculty, name="Computing", code="OSCOMP")
        self.session = AcademicSession.objects.create(
            school=self.school, label="2026/2027", start_date=date(2026, 9, 1), end_date=date(2027, 7, 1)
        )
        self.semester = Semester.objects.create(
            session=self.session,
            name=Semester.SemesterName.FIRST,
            start_date=date(2026, 9, 1), end_date=date(2027, 1, 31),
            lecture_start_date=date(2026, 9, 7), lecture_end_date=date(2026, 12, 1),
            exam_start_date=date(2026, 12, 7), exam_end_date=date(2026, 12, 12),
        )
        self.department_admin_user = User.objects.create_user(
            identifier="EXAM_SCOPE_ADMIN", role=User.Role.ADMIN, password="password", requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.department_admin_user, staff_id="EXAM_SCOPE_ADMIN", full_name="Scope Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.department,
        )
        self.school_admin_user = User.objects.create_user(
            identifier="EXAM_SCHOOL_ADMIN", role=User.Role.ADMIN, password="password", requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.school_admin_user, staff_id="EXAM_SCHOOL_ADMIN", full_name="School Admin",
            level=AdminOfficer.Level.SCHOOL, scope_school=self.school,
        )
        self.faculty_admin_user = User.objects.create_user(
            identifier="EXAM_FACULTY_ADMIN", role=User.Role.ADMIN, password="password", requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.faculty_admin_user, staff_id="EXAM_FACULTY_ADMIN", full_name="Faculty Admin",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty,
        )
        self.course = Course.objects.create(
            code="CSC201", title="Data Structures", level=200, semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.department,
        )
        self.venue = Venue.objects.create(
            name="Optimization Hall", venue_type=Venue.VenueType.EXAM_HALL, capacity=100, exam_capacity=100,
            owning_level=Venue.OwningLevel.DEPARTMENT, owning_department=self.department,
        )
        student_user = User.objects.create_user(identifier="EXAM_STUDENT", role=User.Role.STUDENT, password="password")
        student = Student.objects.create(user=student_user, matric_number="EXAM_STUDENT", full_name="Exam Student", department=self.department, level=200)
        CourseRegistration.objects.create(student=student, course=self.course, academic_session=self.session.label)
        GenerationScopePermission.objects.create(
            school=self.school,
            allow_faculty_exam_generation=True,
            allow_department_exam_generation=True,
        )

    def test_department_admin_cannot_generate_when_policy_disabled(self):
        perm = GenerationScopePermission.objects.get(school=self.school)
        perm.allow_department_exam_generation = False
        perm.save()
        self.client.force_authenticate(self.department_admin_user)
        access = self.client.get("/api/scheduling/exam-optimizer/access/", {
            "semester": self.semester.id, "scope_type": "department", "scope_id": self.department.id,
        })
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["can_view"])
        self.assertFalse(access.data["can_optimize"])
        response = self.client.post("/api/scheduling/exam-optimizer/optimize/", {
            "semester_id": self.semester.id, "scope_type": "department", "scope_id": self.department.id,
        }, format="json")
        self.assertEqual(response.status_code, 403)

    def test_faculty_admin_cannot_generate_when_policy_disabled(self):
        perm = GenerationScopePermission.objects.get(school=self.school)
        perm.allow_faculty_exam_generation = False
        perm.save()
        self.client.force_authenticate(self.faculty_admin_user)
        access = self.client.get("/api/scheduling/exam-optimizer/access/", {
            "semester": self.semester.id, "scope_type": "faculty", "scope_id": self.faculty.id,
        })
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["can_view"])
        self.assertFalse(access.data["can_optimize"])

    def test_scope_admin_can_generate_inspect_approve_and_publish_run(self):
        self.client.force_authenticate(self.department_admin_user)
        response = self.client.post("/api/scheduling/exam-optimizer/optimize/", {
            "semester_id": self.semester.id, "scope_type": "department", "scope_id": self.department.id,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        run_id = response.data["run_id"]
        self.assertEqual(response.data["status"], "draft")
        self.assertEqual(response.data["metrics"]["courses_scheduled"], 1)
        self.assertIn("runtime_seconds", response.data["metrics"])

        detail = self.client.get(f"/api/scheduling/exam-optimizer/runs/{run_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.data["events"]), 1)

        approved = self.client.post(f"/api/scheduling/exam-optimizer/runs/{run_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data["status"], "approved")
        published = self.client.post(f"/api/scheduling/exam-optimizer/runs/{run_id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, 200)
        self.assertEqual(published.data["status"], "published")

        timetable = self.client.get("/api/scheduling/exam-optimizer/timetable/", {
            "semester": self.semester.id, "scope_type": "department", "scope_id": self.department.id,
        })
        self.assertEqual(timetable.status_code, 200)
        self.assertEqual(len(timetable.data["events"]), 1)

    def test_school_admin_has_generator_and_timetable_view_access(self):
        self.client.force_authenticate(self.school_admin_user)
        access = self.client.get("/api/scheduling/exam-optimizer/access/", {
            "semester": self.semester.id, "scope_type": "school", "scope_id": self.school.id,
        })
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["can_optimize"])
        self.assertTrue(access.data["can_view"])

        generated = self.client.post("/api/scheduling/exam-optimizer/optimize/", {
            "semester_id": self.semester.id, "scope_type": "school", "scope_id": self.school.id,
        }, format="json")
        self.assertEqual(generated.status_code, 201, generated.data)
        display = self.client.get("/api/scheduling/exam-optimizer/timetable/", {
            "semester": self.semester.id, "scope_type": "school", "scope_id": self.school.id,
        })
        self.assertEqual(display.status_code, 200)

    def test_faculty_admin_can_generate_when_no_faculty_exam_officer_is_assigned(self):
        self.client.force_authenticate(self.faculty_admin_user)
        access = self.client.get("/api/scheduling/exam-optimizer/access/", {
            "semester": self.semester.id, "scope_type": "faculty", "scope_id": self.faculty.id,
        })
        self.assertEqual(access.status_code, 200)
        self.assertTrue(access.data["can_view"])
        self.assertTrue(access.data["can_optimize"])
        generated = self.client.post("/api/scheduling/exam-optimizer/optimize/", {
            "semester_id": self.semester.id, "scope_type": "faculty", "scope_id": self.faculty.id,
        }, format="json")
        self.assertEqual(generated.status_code, 201, generated.data)
        self.assertEqual(generated.data["metrics"]["courses_scheduled"], 1)

    def test_export_exam_problem_json_and_csv(self):
        self.client.force_authenticate(self.faculty_admin_user)

        # 1. Test JSON export
        res_json = self.client.post("/api/scheduling/exam-optimizer/export-problem/", {
            "semester_id": self.semester.id,
            "scope_type": "faculty",
            "scope_id": self.faculty.id,
            "format": "json",
        }, format="json")
        self.assertEqual(res_json.status_code, 200, res_json.data)
        self.assertIn("metadata", res_json.data)
        self.assertIn("hierarchy", res_json.data)
        self.assertIn("all_events", res_json.data)
        self.assertIn("venues", res_json.data)
        self.assertIn("candidate_windows", res_json.data)
        self.assertIn("student_conflict_graph", res_json.data)

        # 2. Test CSV export
        res_csv = self.client.post("/api/scheduling/exam-optimizer/export-problem/", {
            "semester_id": self.semester.id,
            "scope_type": "faculty",
            "scope_id": self.faculty.id,
            "format": "csv",
        }, format="json")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv["Content-Type"], "text/csv")
        csv_text = res_csv.content.decode("utf-8")
        self.assertIn("Event ID,Course Code,Course Title", csv_text)
        self.assertIn("CSC201", csv_text)

