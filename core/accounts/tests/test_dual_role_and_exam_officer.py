from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, LecturerStaff, User
from courses.models import Course
from hierarchy.models import Department, Faculty, School
from scheduling.models import Semester, AcademicSession, TimetableEntry, ExamSitting
from venues.models import Venue


class DualRoleAndExamOfficerTests(APITestCase):
    def setUp(self):
        # Hierarchy
        self.school = School.objects.create(name="School of Science", code="SOS")
        self.fac = Faculty.objects.create(school=self.school, name="Faculty of Computing", code="FOC")
        self.dept1 = Department.objects.create(faculty=self.fac, name="Computer Science", code="CSC")
        self.dept2 = Department.objects.create(faculty=self.fac, name="Cybersecurity", code="CYB")

        self.other_fac = Faculty.objects.create(school=self.school, name="Faculty of Arts", code="FOA")
        self.other_dept = Department.objects.create(faculty=self.other_fac, name="History", code="HIS")

        # Academic Session & Semester
        self.academic_session = AcademicSession.objects.create(
            school=self.school, label="2026/2027", start_date="2026-09-01", end_date="2027-07-01", is_current=True
        )
        self.semester = Semester.objects.create(
            session=self.academic_session, name=Semester.SemesterName.FIRST,
            start_date="2026-09-01", end_date="2027-01-31",
            lecture_start_date="2026-09-01", lecture_end_date="2026-12-15",
            is_active=True
        )

        # Faculty Admin (Creator)
        self.fac_user = User.objects.create_user(
            identifier="FAC_ADMIN", password="password123",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_user, staff_id="FAC_ADMIN", full_name="Faculty Admin",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.fac,
        )

        # Department Admin (Creator)
        self.dept_user = User.objects.create_user(
            identifier="DEPT_ADMIN", password="password123",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_user, staff_id="DEPT_ADMIN", full_name="Dept Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1,
        )

    def test_create_dual_role_admin_officer(self):
        """Faculty admin creates a department admin who is also a lecturer."""
        self.client.force_authenticate(user=self.fac_user)
        url = reverse("admin-officer-list")
        payload = {
            "staff_id": "DEPT_LEC_01",
            "full_name": "Dr. Dual Role",
            "email": "dual@example.com",
            "level": "department",
            "scope_department": self.dept1.id,
            "is_lecturer": True,
            "lecturer_department": self.dept1.id,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["is_lecturer"])
        self.assertEqual(res.data["lecturer_department_id"], self.dept1.id)

        # Verify LecturerStaff was created for the same user
        admin_obj = AdminOfficer.objects.get(staff_id="DEPT_LEC_01")
        self.assertTrue(hasattr(admin_obj.user, "lecturer_profile"))
        lec = admin_obj.user.lecturer_profile
        self.assertEqual(lec.staff_id, "DEPT_LEC_01")
        self.assertEqual(lec.full_name, "Dr. Dual Role")
        self.assertEqual(lec.department, self.dept1)

        # Verify Course assignment works
        course = Course.objects.create(
            code="CSC101", title="Intro to CS", level=100,
            owning_level="department", owning_department=self.dept1,
        )
        course.lecturers.add(lec)
        self.assertIn(lec, course.lecturers.all())

    def test_lecturer_department_scope_validation(self):
        """Faculty admin cannot assign a lecturer department outside their faculty."""
        self.client.force_authenticate(user=self.fac_user)
        url = reverse("admin-officer-list")
        payload = {
            "staff_id": "INVALID_SCOPE",
            "full_name": "Invalid Scope Officer",
            "email": "invalid@example.com",
            "level": "department",
            "scope_department": self.dept1.id,
            "is_lecturer": True,
            "lecturer_department": self.other_dept.id,  # in other_fac!
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lecturer_department", res.data)

    def test_cannot_remove_lecturer_when_courses_assigned(self):
        """Cannot uncheck is_lecturer if the lecturer is currently assigned to a course."""
        self.client.force_authenticate(user=self.fac_user)
        admin_user = User.objects.create_user(
            identifier="LEC_ADMIN_ACTIVE", password="password123",
            role=User.Role.ADMIN, requires_password_reset=False,
        )
        admin = AdminOfficer.objects.create(
            user=admin_user, staff_id="LEC_ADMIN_ACTIVE", full_name="Assigned Lecturer Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept1,
            is_lecturer=True, lecturer_department=self.dept1,
        )
        lec = LecturerStaff.objects.create(
            user=admin_user, staff_id="LEC_ADMIN_ACTIVE", full_name="Assigned Lecturer Admin",
            department=self.dept1,
        )
        course = Course.objects.create(
            code="CSC201", title="Data Structures", level=200,
            owning_level="department", owning_department=self.dept1,
        )
        course.lecturers.add(lec)

        # Try to update is_lecturer to False
        url = reverse("admin-officer-detail", kwargs={"pk": admin.id})
        res = self.client.patch(url, {"is_lecturer": False}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_lecturer", res.data)

    def test_exam_officer_creation_and_restrictions(self):
        """Exam officer can be created and is barred from lecture timetable generation & reports."""
        self.client.force_authenticate(user=self.fac_user)
        url = reverse("admin-officer-list")
        payload = {
            "staff_id": "EXAM_OFFICER_01",
            "full_name": "Dept Exam Officer",
            "email": "exam@example.com",
            "level": "department",
            "scope_department": self.dept1.id,
            "is_exam_officer": True,
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["is_exam_officer"])

        # Authenticate as the newly created Exam Officer
        exam_user = User.objects.get(identifier="EXAM_OFFICER_01")
        exam_user.requires_password_reset = False
        exam_user.save()
        self.client.force_authenticate(user=exam_user)

        # 1. Blocked from timetable generation
        gen_url = reverse("timetable-generate-list")
        gen_res = self.client.post(gen_url, {"semester": self.semester.id, "scope_type": "department", "scope_id": self.dept1.id}, format="json")
        self.assertEqual(gen_res.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Blocked from lecture attendance reports
        rep_url = reverse("class-rep-report-list")
        rep_res = self.client.get(rep_url)
        self.assertEqual(rep_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(rep_res.data["results"] if isinstance(rep_res.data, dict) else rep_res.data), 0)

        # 3. Blocked from lecture hold rate analytics
        hold_url = reverse("reporting-analytics-lecture-hold-rate")
        hold_res = self.client.get(hold_url)
        self.assertEqual(hold_res.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Allowed exam-specific analytics
        exam_analytics_url = reverse("reporting-analytics-exam-analytics")
        exam_res = self.client.get(exam_analytics_url)
        self.assertEqual(exam_res.status_code, status.HTTP_200_OK)
        self.assertIn("summary", exam_res.data)
        self.assertIn("daily_breakdown", exam_res.data)

        # 5. Role statcards return exam metrics
        statcards_url = reverse("reporting-analytics-dashboard-statcards")
        statcards_res = self.client.get(statcards_url)
        self.assertEqual(statcards_res.status_code, status.HTTP_200_OK)
        cards = statcards_res.data.get("cards", statcards_res.data) if isinstance(statcards_res.data, dict) else statcards_res.data
        card_ids = [c["id"] for c in cards]
        self.assertIn("exam_sittings", card_ids)
        self.assertIn("exam_candidates", card_ids)

