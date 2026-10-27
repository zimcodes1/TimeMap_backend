from datetime import date, time
from django.test import TestCase
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, LecturerStaff, Student, User
from courses.models import Course, CourseRegistration
from hierarchy.models import Department, Faculty, Program, School
from scheduling.exam_optimizer.generator import generate_exam_timetable
from scheduling.models import (
    AcademicSession,
    ExamOptimizerRun,
    GenerationScopePermission,
    Semester,
    TimetableGenerationRun,
)
from scheduling.optimizer.generator import generate_timetable
from scheduling.optimizer.preprocessing.pipeline import build_scheduling_problem_from_db
from venues.models import Venue


class ScopeAwareOptimizersVerificationTests(APITestCase):
    """
    Comprehensive verification test suite verifying scope-awareness across:
    - Lecture Optimizer (Genetic Algorithm)
    - Exam Optimizer (Heuristic Placement & Room Allocation)
    Covers sibling departments, ancestor scopes, shared lecturers, shared cohorts,
    and graceful failure / saturation diagnostics.
    """

    def setUp(self):
        self.school = School.objects.create(name="Scope Uni", code="SUNI")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSIC")
        self.dept_cs = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CS")
        self.dept_ee = Department.objects.create(faculty=self.faculty, name="Electrical Eng", code="EE")

        self.prog_cs = Program.objects.filter(department=self.dept_cs, is_default=True).first()
        self.prog_ee = Program.objects.filter(department=self.dept_ee, is_default=True).first()

        self.session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 1),
        )
        self.semester = Semester.objects.create(
            session=self.session,
            name=Semester.SemesterName.FIRST,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 1, 31),
            lecture_start_date=date(2026, 9, 7),
            lecture_end_date=date(2026, 12, 1),
            exam_start_date=date(2026, 12, 7),
            exam_end_date=date(2026, 12, 12),
        )

        GenerationScopePermission.objects.create(
            school=self.school,
            allow_faculty_exam_generation=True,
            allow_department_exam_generation=True,
        )

        # Shared Auditorium and Shared CBT Lab
        self.shared_hall = Venue.objects.create(
            name="University Auditorium",
            venue_type=Venue.VenueType.LECTURE_HALL,
            capacity=200,
            exam_capacity=200,
            owning_level=Venue.OwningLevel.SCHOOL,
            owning_school=self.school,
        )
        self.cbt_center = Venue.objects.create(
            name="Central CBT Center",
            venue_type=Venue.VenueType.CBT_CENTER,
            capacity=100,
            exam_capacity=100,
            owning_level=Venue.OwningLevel.SCHOOL,
            owning_school=self.school,
        )

        # Lecturer teaching across departments
        user_prof = User.objects.create_user(identifier="PROF_K", role=User.Role.LECTURER, password="password", requires_password_reset=False)
        self.prof_k = LecturerStaff.objects.create(
            user=user_prof,
            department=self.dept_cs,
            staff_id="PROF_K",
            full_name="Prof John Kasim",
        )

        # Admin users for API publishing tests
        self.school_admin_user = User.objects.create_user(identifier="SCH_ADMIN", role=User.Role.ADMIN, password="password", requires_password_reset=False)
        AdminOfficer.objects.create(user=self.school_admin_user, staff_id="SCH_ADMIN", full_name="School Admin", level=AdminOfficer.Level.SCHOOL, scope_school=self.school)
        self.cs_admin_user = User.objects.create_user(identifier="CS_ADMIN", role=User.Role.ADMIN, password="password", requires_password_reset=False)
        AdminOfficer.objects.create(user=self.cs_admin_user, staff_id="CS_ADMIN", full_name="CS Admin", level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept_cs)

    def test_t1_exam_optimizer_sibling_department_scope_awareness_success(self):
        """
        T1: Dept CS publishes an exam timetable using Central CBT Center on 2026-12-07 08:00-10:00.
        Dept EE generates an exam timetable requiring Central CBT Center.
        EE's optimizer must avoid 2026-12-07 08:00-10:00 and schedule in an unblocked window.
        """
        # 1. Dept CS course
        course_cs = Course.objects.create(
            code="CSC201",
            title="Data Structures",
            level=200,
            exam_type=Course.ExamType.CBT,
            exam_duration_per_student_minutes=30,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept_cs,
            target_program=self.prog_cs,
        )
        u1 = User.objects.create_user(identifier="STU_CS_1", role=User.Role.STUDENT, password="password", requires_password_reset=False)
        s1 = Student.objects.create(user=u1, matric_number="STU_CS_1", full_name="CS Student", department=self.dept_cs, level=200)
        CourseRegistration.objects.create(student=s1, course=course_cs, academic_session=self.session.label)

        # Publish Dept CS exam run occupying 2026-12-07 08:00 to 10:00
        ExamOptimizerRun.objects.create(
            semester=self.semester,
            scope_type=ExamOptimizerRun.ScopeType.DEPARTMENT,
            scope_id=self.dept_cs.id,
            status=ExamOptimizerRun.Status.PUBLISHED,
            events=[
                {
                    "course_id": course_cs.id,
                    "course_code": "CSC201",
                    "course_level": 200,
                    "department_id": self.dept_cs.id,
                    "program_id": self.prog_cs.id,
                    "exam_type": Course.ExamType.CBT,
                    "date": "2026-12-07",
                    "start_time": "08:00:00",
                    "end_time": "10:00:00",
                    "student_count": 50,
                    "venues": [{"venue_id": self.cbt_center.id, "venue_name": self.cbt_center.name, "students": 50, "turns": 1, "capacity": 100}],
                }
            ],
        )

        # 2. Dept EE course (also CBT in Central CBT Center)
        course_ee = Course.objects.create(
            code="EEE201",
            title="Circuits I",
            level=200,
            exam_type=Course.ExamType.CBT,
            exam_duration_per_student_minutes=30,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept_ee,
            target_program=self.prog_ee,
        )
        u2 = User.objects.create_user(identifier="STU_EE_1", role=User.Role.STUDENT, password="password", requires_password_reset=False)
        s2 = Student.objects.create(user=u2, matric_number="STU_EE_1", full_name="EE Student", department=self.dept_ee, level=200)
        CourseRegistration.objects.create(student=s2, course=course_ee, academic_session=self.session.label)

        # 3. Generate exam timetable for Dept EE
        ee_result = generate_exam_timetable(
            semester=self.semester,
            scope_type="department",
            scope_id=self.dept_ee.id,
        )

        self.assertTrue(ee_result.is_feasible)
        self.assertEqual(len(ee_result.events), 1)
        ee_event = ee_result.events[0]
        self.assertEqual(ee_event["course_code"], "EEE201")

        # Must NOT be scheduled on 2026-12-07 between 08:00 and 10:00
        is_colliding = (
            ee_event["date"] == "2026-12-07"
            and ee_event["start_time"] < "10:00:00"
            and ee_event["end_time"] > "08:00:00"
        )
        self.assertFalse(is_colliding, "EEE201 should avoid 2026-12-07 08:00-10:00 occupied by CSC201!")

    def test_t2_exam_optimizer_sibling_department_saturation_failure(self):
        """
        T2: When external published runs occupy all candidate windows for a scarce venue,
        the optimizer gracefully records the event in unscheduled with a descriptive reason.
        """
        # Create a 2-day exam semester
        short_semester = Semester.objects.create(
            session=self.session,
            name=Semester.SemesterName.SECOND,
            start_date=date(2027, 2, 1),
            end_date=date(2027, 6, 30),
            lecture_start_date=date(2027, 2, 1),
            lecture_end_date=date(2027, 2, 28),
            exam_start_date=date(2027, 3, 1),
            exam_end_date=date(2027, 3, 2),  # 2 days
        )
        single_cbt = Venue.objects.create(
            name="Isolated CBT Lab",
            venue_type=Venue.VenueType.CBT_CENTER,
            capacity=50,
            exam_capacity=50,
            owning_level=Venue.OwningLevel.DEPARTMENT,
            owning_department=self.dept_ee,
        )

        # Dept CS has an external run occupying the entire day 08:00-18:00 on both days in that venue
        ExamOptimizerRun.objects.create(
            semester=short_semester,
            scope_type=ExamOptimizerRun.ScopeType.DEPARTMENT,
            scope_id=self.dept_cs.id,
            status=ExamOptimizerRun.Status.PUBLISHED,
            events=[
                {
                    "course_id": 9999,
                    "course_code": "CSC_SATURATE_1",
                    "date": "2027-03-01",
                    "start_time": "08:00:00",
                    "end_time": "18:00:00",
                    "student_count": 50,
                    "venues": [{"venue_id": single_cbt.id, "venue_name": single_cbt.name, "students": 50}],
                },
                {
                    "course_id": 9998,
                    "course_code": "CSC_SATURATE_2",
                    "date": "2027-03-02",
                    "start_time": "08:00:00",
                    "end_time": "18:00:00",
                    "student_count": 50,
                    "venues": [{"venue_id": single_cbt.id, "venue_name": single_cbt.name, "students": 50}],
                },
            ],
        )

        # Dept EE course needing CBT
        c = Course.objects.create(
            code="EEE301",
            title="Signals",
            level=300,
            exam_type=Course.ExamType.CBT,
            exam_duration_per_student_minutes=30,
            semester=short_semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept_ee,
        )
        u = User.objects.create_user(identifier="STU_SAT", role=User.Role.STUDENT, password="password", requires_password_reset=False)
        st = Student.objects.create(user=u, matric_number="STU_SAT", full_name="Sat Stu", department=self.dept_ee, level=300)
        CourseRegistration.objects.create(student=st, course=c, academic_session=self.session.label)

        # Deactivate the shared school CBT center so single_cbt is the sole CBT venue available
        self.cbt_center.is_active = False
        self.cbt_center.save()

        try:
            result = generate_exam_timetable(
                semester=short_semester,
                scope_type="department",
                scope_id=self.dept_ee.id,
            )

            # Because the single venue is 100% blocked on both days, the course cannot be placed
            self.assertFalse(result.is_feasible)
            self.assertEqual(result.status, "BEST_AVAILABLE")
            self.assertEqual(len(result.events), 0)
            # Diagnostics must capture unscheduled event
            unscheduled_list = result.diagnostics.get("unscheduled", [])
            self.assertTrue(len(unscheduled_list) > 0)
            self.assertEqual(unscheduled_list[0]["course_code"], "EEE301")
        finally:
            self.cbt_center.is_active = True
            self.cbt_center.save()

    def test_t3_lecture_optimizer_shared_lecturer_scope_awareness_success(self):
        """
        T3: Faculty publishes timetable where Prof K teaches a Faculty course at MO_08:00-10:00.
        Dept CS generates timetable for CSC301 where Prof K is the lecturer.
        CS optimizer must avoid MO_08:00-10:00 for CSC301.
        """
        # 1. Faculty-level course taught by Prof K
        fac_course = Course.objects.create(
            code="SCI101",
            title="Foundation Science",
            level=100,
            semester=self.semester,
            owning_level=Course.OwningLevel.FACULTY,
            owning_faculty=self.faculty,
        )
        fac_course.lecturers.add(self.prof_k)

        # Publish a Faculty TimetableGenerationRun placing SCI101 at MO_08:00-10:00
        TimetableGenerationRun.objects.create(
            semester=self.semester,
            scope_type=TimetableGenerationRun.ScopeType.FACULTY,
            scope_id=self.faculty.id,
            scope_name=self.faculty.name,
            status=TimetableGenerationRun.Status.COMPLETED,
            is_published=True,
            assignments_payload=[
                {
                    "course_id": fac_course.id,
                    "course_code": "SCI101",
                    "day": "MO",
                    "start_time": "08:00:00",
                    "end_time": "10:00:00",
                    "venue_id": self.shared_hall.id,
                    "venue_name": self.shared_hall.name,
                    "lecturer_ids": [self.prof_k.id],
                    "programs": [],
                }
            ],
        )

        # 2. Dept CS course taught by Prof K
        cs_course = Course.objects.create(
            code="CSC301",
            title="Operating Systems",
            level=300,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept_cs,
            target_program=self.prog_cs,
            required_occurrences_per_week=1,
        )
        cs_course.lecturers.add(self.prof_k)

        problem = build_scheduling_problem_from_db(
            semester_id=self.semester.id,
            scope_type="department",
            scope_id=self.dept_cs.id,
        )

        # Prof K must be in blocked_lecturer_slots for MO_08:00-10:00
        self.assertIn(self.prof_k.id, problem.blocked_lecturer_slots)
        self.assertIn("MO_08:00-10:00", problem.blocked_lecturer_slots[self.prof_k.id])

        # Run optimizer
        result = generate_timetable(problem)
        self.assertTrue(result.is_feasible)
        self.assertEqual(len(result.assignments), 1)

        placed_slot = result.assignments[0].slot.slot_id
        self.assertNotEqual(placed_slot, "MO_08:00-10:00", "CSC301 must not be scheduled at MO_08:00-10:00 when Prof K is busy!")

    def test_t4_lecture_optimizer_shared_cohort_scope_awareness(self):
        """
        T4: Sibling Dept EE publishes a timetable for an inter-departmental course
        attended by CS 200L cohort at TU_10:00-12:00.
        Dept CS generates timetable: CS courses for 200L must avoid TU_10:00-12:00.
        """
        TimetableGenerationRun.objects.create(
            semester=self.semester,
            scope_type=TimetableGenerationRun.ScopeType.DEPARTMENT,
            scope_id=self.dept_ee.id,
            scope_name=self.dept_ee.name,
            status=TimetableGenerationRun.Status.COMPLETED,
            is_published=True,
            assignments_payload=[
                {
                    "course_id": 8888,
                    "course_code": "EEE_SHARED",
                    "day": "TU",
                    "start_time": "10:00:00",
                    "end_time": "12:00:00",
                    "venue_id": self.shared_hall.id,
                    "venue_name": self.shared_hall.name,
                    "lecturer_ids": [],
                    "programs": [
                        {"id": self.prog_cs.id, "level": 200, "name": self.prog_cs.name}
                    ],
                }
            ],
        )

        # Dept CS generates for CS 200L
        cs201 = Course.objects.create(
            code="CSC201_LEC",
            title="Data Structures Lecture",
            level=200,
            semester=self.semester,
            owning_level=Course.OwningLevel.DEPARTMENT,
            owning_department=self.dept_cs,
            target_program=self.prog_cs,
            required_occurrences_per_week=1,
        )

        problem = build_scheduling_problem_from_db(
            semester_id=self.semester.id,
            scope_type="department",
            scope_id=self.dept_cs.id,
        )

        cohort_key = (self.prog_cs.id, 200)
        self.assertIn(cohort_key, problem.blocked_cohort_slots)
        self.assertIn("TU_10:00-12:00", problem.blocked_cohort_slots[cohort_key])

        result = generate_timetable(problem)
        self.assertTrue(result.is_feasible)
        placed_slot = result.assignments[0].slot.slot_id
        self.assertNotEqual(placed_slot, "TU_10:00-12:00", "CS 200L must avoid TU_10:00-12:00 pre-occupied by sibling timetable!")

    def test_t5_exam_optimizer_cascade_publishing_unpublishes_subscopes(self):
        """
        T5: Dept CS has a published exam run.
        School admin publishes a School-level exam run.
        Dept CS run must be transitioned to APPROVED (unpublished),
        and the School run becomes PUBLISHED.
        """
        cs_run = ExamOptimizerRun.objects.create(
            semester=self.semester,
            scope_type=ExamOptimizerRun.ScopeType.DEPARTMENT,
            scope_id=self.dept_cs.id,
            status=ExamOptimizerRun.Status.PUBLISHED,
            events=[],
        )
        school_run = ExamOptimizerRun.objects.create(
            semester=self.semester,
            scope_type=ExamOptimizerRun.ScopeType.SCHOOL,
            scope_id=self.school.id,
            status=ExamOptimizerRun.Status.APPROVED,
            events=[],
        )

        self.client.force_authenticate(user=self.school_admin_user)
        pub_res = self.client.post(f"/api/scheduling/exam-optimizer/runs/{school_run.id}/publish/", format="json")
        self.assertEqual(pub_res.status_code, 200)

        cs_run.refresh_from_db()
        school_run.refresh_from_db()

        self.assertEqual(school_run.status, ExamOptimizerRun.Status.PUBLISHED)
        self.assertEqual(cs_run.status, ExamOptimizerRun.Status.APPROVED, "Department run must be cascade-unpublished when School publishes!")
