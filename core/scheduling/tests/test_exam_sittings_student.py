from datetime import date
from rest_framework.test import APITestCase
from accounts.models import Student, User
from courses.models import Course, CourseRegistration
from hierarchy.models import Department, Faculty, Program, School
from scheduling.models import AcademicSession, ExamOptimizerRun, Semester


class StudentExamSittingsAPITests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Science University", code="SU")
        self.faculty = Faculty.objects.create(school=self.school, name="Computing Faculty", code="CF")
        self.department = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CS")
        self.program = Program.objects.filter(department=self.department, is_default=True).first()
        if not self.program:
            self.program = Program.objects.create(
                department=self.department,
                name="B.Sc Computer Science",
                code="CS_BSC",
                duration_years=4,
                is_default=True,
            )

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
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            lecture_start_date=date(2026, 9, 15),
            lecture_end_date=date(2026, 12, 15),
            exam_start_date=date(2026, 12, 16),
            exam_end_date=date(2027, 1, 15),
            is_active=True,
        )

        # Student user
        self.student_user = User.objects.create_user(
            identifier="STU_TEST_001",
            role=User.Role.STUDENT,
            password="password123",
            requires_password_reset=False,
        )
        self.student = Student.objects.create(
            user=self.student_user,
            matric_number="STU_TEST_001",
            full_name="Alice Student",
            department=self.department,
            program=self.program,
            level=200,
        )

        # Other student from another department
        self.other_dept = Department.objects.create(faculty=self.faculty, name="Maths", code="MATH")
        self.other_prog = Program.objects.filter(department=self.other_dept, is_default=True).first()
        if not self.other_prog:
            self.other_prog = Program.objects.create(
                department=self.other_dept,
                name="B.Sc Mathematics",
                code="MATH_BSC",
                duration_years=4,
                is_default=True,
            )
        self.other_user = User.objects.create_user(
            identifier="STU_MATH_001",
            role=User.Role.STUDENT,
            password="password123",
            requires_password_reset=False,
        )
        self.other_student = Student.objects.create(
            user=self.other_user,
            matric_number="STU_MATH_001",
            full_name="Bob Math",
            department=self.other_dept,
            program=self.other_prog,
            level=200,
        )

        # Courses
        self.course_cs = Course.objects.create(
            code="CSC201",
            title="Data Structures",
            level=200,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.department,
        )
        self.course_math = Course.objects.create(
            code="MTH201",
            title="Linear Algebra",
            level=200,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.other_dept,
        )

        # Create published ExamOptimizerRun
        self.exam_run = ExamOptimizerRun.objects.create(
            semester=self.semester,
            scope_type=ExamOptimizerRun.ScopeType.SCHOOL,
            scope_id=self.school.id,
            status=ExamOptimizerRun.Status.PUBLISHED,
            events=[
                {
                    "course_id": self.course_cs.id,
                    "course_code": "CSC201",
                    "course_title": "Data Structures",
                    "course_level": 200,
                    "exam_type": "cbt",
                    "student_count": 80,
                    "date": "2026-12-18",
                    "start_time": "08:30:00",
                    "end_time": "10:30:00",
                    "duration_minutes": 120,
                    "venues": [
                        {"venue_id": 1, "venue_name": "CBT Center Hall A", "students": 80, "capacity": 100}
                    ],
                },
                {
                    "course_id": self.course_math.id,
                    "course_code": "MTH201",
                    "course_title": "Linear Algebra",
                    "course_level": 200,
                    "exam_type": "written",
                    "student_count": 50,
                    "date": "2026-12-20",
                    "start_time": "11:00:00",
                    "end_time": "13:00:00",
                    "duration_minutes": 120,
                    "venues": [
                        {"venue_id": 2, "venue_name": "Lecture Hall 1", "students": 50, "capacity": 60}
                    ],
                },
            ],
        )

    def test_student_can_fetch_own_exams(self):
        self.client.force_authenticate(user=self.student_user)
        resp = self.client.get("/api/scheduling/exam-sittings/my-exams/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["course"]["code"], "CSC201")
        self.assertEqual(data[0]["date"], "2026-12-18")
        self.assertEqual(data[0]["exam_type"], "cbt")
        self.assertTrue(data[0]["is_exam"])
        self.assertEqual(data[0]["venue"]["name"], "CBT Center Hall A")

    def test_student_list_delegates_to_my_exams(self):
        self.client.force_authenticate(user=self.student_user)
        resp = self.client.get("/api/scheduling/exam-sittings/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["course"]["code"], "CSC201")

    def test_other_student_sees_their_own_exams(self):
        self.client.force_authenticate(user=self.other_user)
        resp = self.client.get("/api/scheduling/exam-sittings/my-exams/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["course"]["code"], "MTH201")
        self.assertEqual(data[0]["date"], "2026-12-20")

    def test_date_range_filtering(self):
        self.client.force_authenticate(user=self.student_user)
        # Filter for a date range that misses the exam
        resp = self.client.get("/api/scheduling/exam-sittings/my-exams/?start_date=2026-12-25&end_date=2026-12-30")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 0)

        # Filter for range that covers the exam
        resp2 = self.client.get("/api/scheduling/exam-sittings/my-exams/?start_date=2026-12-15&end_date=2026-12-19")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.json()), 1)

