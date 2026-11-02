import datetime
from accounts.models import AdminOfficer, Student, User
from courses.models import Course, CourseAccessGrant
from hierarchy.models import Department, Faculty, Program, School
from rest_framework import status
from rest_framework.test import APITestCase
from scheduling.models import AcademicSession, LectureSession, Semester, TimetableEntry
from venues.models import Venue


class SharedAndLeasedCoursesScheduleTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="State University", code="SU")
        self.academic_session = AcademicSession.objects.create(
            school=self.school,
            label="2026/2027",
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 7, 31),
            is_current=True,
        )
        self.semester = Semester.objects.create(
            session=self.academic_session,
            name=Semester.SemesterName.FIRST,
            start_date=datetime.date(2026, 9, 1),
            end_date=datetime.date(2027, 1, 31),
            lecture_start_date=datetime.date(2026, 9, 1),
            lecture_end_date=datetime.date(2026, 12, 20),
            is_active=True,
        )

        # Faculty 1: Science & Faculty 2: Social Sciences
        self.fac_sci = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.fac_soc = Faculty.objects.create(school=self.school, name="Faculty of Social Sciences", code="FSS")

        # Departments
        self.dept_cs = Department.objects.create(faculty=self.fac_sci, name="Computer Science", code="CSC")
        self.dept_soc = Department.objects.create(faculty=self.fac_soc, name="Sociology", code="SOC")

        # Program under Sociology
        self.prog_crim = Program.objects.create(department=self.dept_soc, name="Criminology", code="CRM")

        # Admins
        self.uni_admin_user = User.objects.create_user(
            identifier="UNI_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        AdminOfficer.objects.create(
            user=self.uni_admin_user, staff_id="UNI_ADMIN", full_name="Uni Admin", level=AdminOfficer.Level.UNIVERSITY
        )

        self.soc_admin_user = User.objects.create_user(
            identifier="SOC_ADMIN", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.soc_admin = AdminOfficer.objects.create(
            user=self.soc_admin_user, staff_id="SOC_ADMIN", full_name="Soc Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.dept_soc
        )

        # Student in Criminology Level 100
        self.student_user = User.objects.create_user(
            identifier="STU_CRM100", password="password", role=User.Role.STUDENT, requires_password_reset=False
        )
        self.student = Student.objects.create(
            user=self.student_user, matric_number="CRM/2026/001", full_name="Criminology Student",
            department=self.dept_soc, program=self.prog_crim, level=100
        )

        # Venues
        self.venue_soc = Venue.objects.create(
            name="SOC Hall 1", venue_type="lecture_hall", capacity=150,
            owning_level="department", owning_department=self.dept_soc
        )
        self.venue_sci = Venue.objects.create(
            name="SCI Lab 1", venue_type="lab", capacity=80,
            owning_level="department", owning_department=self.dept_cs
        )

        # 1. Department owned course (Sociology)
        self.course_soc = Course.objects.create(
            code="SOC101", title="Intro to Sociology", level=100,
            owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.dept_soc,
            semester=self.semester
        )
        # 2. Faculty foundation course (Social Sciences)
        self.course_eco = Course.objects.create(
            code="ECO101", title="Principles of Economics", level=100,
            owning_level=Course.OwningLevel.FACULTY, owning_faculty=self.fac_soc,
            semester=self.semester
        )
        # 3. Leased course (owned by CS in Science, leased to Sociology)
        self.course_sta = Course.objects.create(
            code="STA101", title="Elementary Statistics", level=100,
            owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.dept_cs,
            semester=self.semester
        )
        CourseAccessGrant.objects.create(
            course=self.course_sta,
            granted_to_level=CourseAccessGrant.GrantedToLevel.DEPARTMENT,
            granted_to_department=self.dept_soc,
            direction=CourseAccessGrant.Direction.OFFERED,
            status=CourseAccessGrant.Status.APPROVED,
            initiated_by=self.soc_admin,
        )
        # 4. University-wide GST general course
        self.course_gst = Course.objects.create(
            code="GST111", title="Communication in English", level=100,
            owning_level=Course.OwningLevel.GENERAL,
            semester=self.semester
        )
        # 5. Unrelated Science course (Chemistry / CS - not leased to Sociology)
        self.course_chm = Course.objects.create(
            code="CHM101", title="General Chemistry", level=100,
            owning_level=Course.OwningLevel.DEPARTMENT, owning_department=self.dept_cs,
            semester=self.semester
        )

        # Create Timetable Entries and Sessions for all 5 courses
        today = datetime.date.today()
        self.entry_soc = self._create_entry_and_session(self.course_soc, self.venue_soc, "08:00:00", "10:00:00", today)
        self.entry_eco = self._create_entry_and_session(self.course_eco, self.venue_soc, "10:00:00", "12:00:00", today)
        self.entry_sta = self._create_entry_and_session(self.course_sta, self.venue_soc, "12:00:00", "14:00:00", today)
        self.entry_gst = self._create_entry_and_session(self.course_gst, self.venue_soc, "14:00:00", "16:00:00", today)
        self.entry_chm = self._create_entry_and_session(self.course_chm, self.venue_sci, "08:00:00", "10:00:00", today)

    def _create_entry_and_session(self, course, venue, start_t, end_t, session_date):
        entry = TimetableEntry.objects.create(
            entry_type=TimetableEntry.EntryType.LECTURE,
            title=f"{course.code} Lecture",
            course=course,
            venue=venue,
            start_time=start_t,
            end_time=end_t,
            created_by=self.soc_admin,
            semester=self.semester,
            status=TimetableEntry.Status.SCHEDULED,
        )
        session = LectureSession.objects.create(
            timetable_entry=entry,
            session_date=session_date,
            session_start_time=start_t,
            session_end_time=end_t,
            venue=venue,
            status=LectureSession.Status.SCHEDULED,
        )
        return entry

    def test_department_filter_includes_leased_and_gst_courses(self):
        """
        GET /api/scheduling/entries/?department=<id> must include:
        - Owned course (SOC101)
        - Faculty foundation course (ECO101)
        - Leased course (STA101)
        - General / GST course (GST111)
        Must NOT include unrelated courses (CHM101).
        """
        self.client.force_authenticate(user=self.uni_admin_user)
        res = self.client.get("/api/scheduling/entries/", {
            "department": self.dept_soc.id,
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_courses = {e["course"] for e in res.data if e.get("course")}

        self.assertIn(self.course_soc.id, returned_courses, "Owned course must appear")
        self.assertIn(self.course_eco.id, returned_courses, "Faculty course must appear")
        self.assertIn(self.course_sta.id, returned_courses, "Leased course must appear")
        self.assertIn(self.course_gst.id, returned_courses, "GST course must appear")
        self.assertNotIn(self.course_chm.id, returned_courses, "Unrelated course must not appear")

    def test_department_filter_sessions_includes_leased_and_gst_courses(self):
        """
        GET /api/scheduling/sessions/?department=<id> must include sessions for:
        - Owned course (SOC101)
        - Faculty foundation course (ECO101)
        - Leased course (STA101)
        - General / GST course (GST111)
        Must NOT include unrelated courses (CHM101).
        """
        self.client.force_authenticate(user=self.uni_admin_user)
        res = self.client.get("/api/scheduling/sessions/", {
            "department": self.dept_soc.id,
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_entry_ids = {
            s["timetable_entry"]["id"] if isinstance(s["timetable_entry"], dict) else s["timetable_entry"]
            for s in res.data if s.get("timetable_entry")
        }

        self.assertIn(self.entry_soc.id, returned_entry_ids)
        self.assertIn(self.entry_eco.id, returned_entry_ids)
        self.assertIn(self.entry_sta.id, returned_entry_ids)
        self.assertIn(self.entry_gst.id, returned_entry_ids)
        self.assertNotIn(self.entry_chm.id, returned_entry_ids)

    def test_program_and_level_filter_includes_leased_and_gst(self):
        """
        GET /api/scheduling/entries/?department=<id>&program=<id>&level=100
        Simulates user selecting Department, Program, and Level on Web Schedule page.
        Must return SOC101, ECO101, STA101, GST111.
        """
        self.client.force_authenticate(user=self.uni_admin_user)
        res = self.client.get("/api/scheduling/entries/", {
            "department": self.dept_soc.id,
            "program": self.prog_crim.id,
            "level": 100,
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_courses = {e["course"] for e in res.data if e.get("course")}

        self.assertIn(self.course_soc.id, returned_courses)
        self.assertIn(self.course_eco.id, returned_courses)
        self.assertIn(self.course_sta.id, returned_courses)
        self.assertIn(self.course_gst.id, returned_courses)
        self.assertNotIn(self.course_chm.id, returned_courses)

    def test_faculty_filter_includes_department_leased_and_gst(self):
        """
        GET /api/scheduling/entries/?faculty=<id> must include:
        - Department course (SOC101)
        - Faculty course (ECO101)
        - Leased course to department (STA101)
        - General / GST course (GST111)
        Must NOT include ungranted Science courses (CHM101).
        """
        self.client.force_authenticate(user=self.uni_admin_user)
        res = self.client.get("/api/scheduling/entries/", {
            "faculty": self.fac_soc.id,
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_courses = {e["course"] for e in res.data if e.get("course")}

        self.assertIn(self.course_soc.id, returned_courses)
        self.assertIn(self.course_eco.id, returned_courses)
        self.assertIn(self.course_sta.id, returned_courses)
        self.assertIn(self.course_gst.id, returned_courses)
        self.assertNotIn(self.course_chm.id, returned_courses)

    def test_department_admin_base_scope_includes_leased_and_gst(self):
        """
        When a Department Admin calls GET /api/scheduling/entries/ without params,
        their base queryset must include their leased and GST courses,
        and exclude ungranted courses from other departments.
        """
        self.client.force_authenticate(user=self.soc_admin_user)
        res = self.client.get("/api/scheduling/entries/", {
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_courses = {e["course"] for e in res.data if e.get("course")}

        self.assertIn(self.course_soc.id, returned_courses)
        self.assertIn(self.course_eco.id, returned_courses)
        self.assertIn(self.course_sta.id, returned_courses)
        self.assertIn(self.course_gst.id, returned_courses)
        self.assertNotIn(self.course_chm.id, returned_courses)

    def test_student_sees_leased_and_gst_courses_on_schedule(self):
        """
        When a Criminology Level 100 student queries GET /api/scheduling/sessions/,
        it must return sessions for SOC101, ECO101, STA101, and GST111.
        """
        self.client.force_authenticate(user=self.student_user)
        res = self.client.get("/api/scheduling/sessions/", {
            "semester": self.semester.id,
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_entry_ids = {
            s["timetable_entry"]["id"] if isinstance(s["timetable_entry"], dict) else s["timetable_entry"]
            for s in res.data if s.get("timetable_entry")
        }

        self.assertIn(self.entry_soc.id, returned_entry_ids, "Student must see owned course")
        self.assertIn(self.entry_eco.id, returned_entry_ids, "Student must see faculty foundation course")
        self.assertIn(self.entry_sta.id, returned_entry_ids, "Student must see leased course")
        self.assertIn(self.entry_gst.id, returned_entry_ids, "Student must see GST course")
        self.assertNotIn(self.entry_chm.id, returned_entry_ids, "Student must not see ungranted course")

    def test_undoing_grant_removes_schedules_from_department_and_students(self):
        """
        When the recipient admin (Sociology) undoes the grant for STA101:
        1. The grant is deleted via POST /api/courses/grants/{id}/cancel/.
        2. Department admin timetable (GET /api/scheduling/entries/) NO LONGER includes STA101.
        3. Program level timetable (GET /api/scheduling/entries/?program=...) NO LONGER includes STA101.
        4. Student schedule (GET /api/scheduling/sessions/) NO LONGER includes STA101.
        """
        grant = CourseAccessGrant.objects.get(
            course=self.course_sta,
            granted_to_department=self.dept_soc,
            status=CourseAccessGrant.Status.APPROVED,
        )

        # Sociology Admin undoes the grant
        self.client.force_authenticate(user=self.soc_admin_user)
        cancel_res = self.client.post(f"/api/courses/grants/{grant.id}/cancel/")
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)
        self.assertFalse(CourseAccessGrant.objects.filter(id=grant.id).exists())

        # 1. Check Department Admin timetable view -> STA101 is gone
        dept_res = self.client.get("/api/scheduling/entries/", {
            "department": self.dept_soc.id,
            "semester": self.semester.id,
        })
        self.assertEqual(dept_res.status_code, status.HTTP_200_OK)
        dept_courses = {e["course"] for e in dept_res.data if e.get("course")}
        self.assertNotIn(self.course_sta.id, dept_courses, "STA101 must be unavailable on department timetable after undo")

        # 2. Check Program level timetable view -> STA101 is gone
        prog_res = self.client.get("/api/scheduling/entries/", {
            "program": self.prog_crim.id,
            "semester": self.semester.id,
        })
        self.assertEqual(prog_res.status_code, status.HTTP_200_OK)
        prog_courses = {e["course"] for e in prog_res.data if e.get("course")}
        self.assertNotIn(self.course_sta.id, prog_courses, "STA101 must be unavailable on program timetable after undo")

        # 3. Check Student schedules view -> STA101 sessions are gone
        self.client.force_authenticate(user=self.student_user)
        student_res = self.client.get("/api/scheduling/sessions/", {
            "semester": self.semester.id,
        })
        self.assertEqual(student_res.status_code, status.HTTP_200_OK)
        student_entry_ids = {
            s["timetable_entry"]["id"] if isinstance(s["timetable_entry"], dict) else s["timetable_entry"]
            for s in student_res.data if s.get("timetable_entry")
        }
        self.assertNotIn(self.entry_sta.id, student_entry_ids, "STA101 must be unavailable on student schedule after undo")
        self.assertIn(self.entry_soc.id, student_entry_ids, "Student still sees regular owned course")
