import tempfile
import os
from django.core.management import call_command
from django.test import TestCase

from accounts.models import AdminOfficer, LecturerStaff, Student, User
from hierarchy.models import Department, Faculty, School


class ImportSeedDataTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Nasarawa State University", code="NSUK")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Natural Sciences", code="FNS")
        self.dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")

    def test_import_students_csv(self):
        content = (
            "matric_number,full_name,department_code,level,is_class_rep,email\n"
            "NSUK/CSC/2021/100,Alice Smith,CSC,300,true,alice@example.com\n"
            "NSUK/CSC/2021/101,Bob Jones,CSC,300,false,bob@example.com\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            call_command("import_seed_data", students_csv=tmp_path)

            self.assertEqual(User.objects.filter(role=User.Role.STUDENT).count(), 2)
            student1 = Student.objects.get(matric_number="NSUK/CSC/2021/100")
            self.assertEqual(student1.full_name, "Alice Smith")
            self.assertTrue(student1.is_class_rep)
            self.assertTrue(student1.user.requires_password_reset)
            self.assertTrue(student1.user.check_password("Pass#1100"))
        finally:
            os.remove(tmp_path)

    def test_import_staff_csv(self):
        content = (
            "staff_id,full_name,role,department_code,admin_level,faculty_code,school_code,email\n"
            "STAFF/001,Dr. John,lecturer,CSC,,,john@example.com\n"
            "STAFF/002,Prof. Admin,admin,CSC,department,,admin@example.com\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            call_command("import_seed_data", staff_csv=tmp_path)

            self.assertEqual(LecturerStaff.objects.count(), 1)
            self.assertEqual(AdminOfficer.objects.count(), 1)

            lecturer = LecturerStaff.objects.get(staff_id="STAFF/001")
            self.assertEqual(lecturer.full_name, "Dr. John")

            admin = AdminOfficer.objects.get(staff_id="STAFF/002")
            self.assertEqual(admin.level, AdminOfficer.Level.DEPARTMENT)
            self.assertEqual(admin.scope_department, self.dept)
        finally:
            os.remove(tmp_path)
