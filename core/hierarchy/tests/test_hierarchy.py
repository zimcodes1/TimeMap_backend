from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from hierarchy.models import Department, Faculty, School


class HierarchyModelTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Nasarawa State University", code="NSUK")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Natural Sciences", code="FNS")

    def test_code_canonical_uppercase_conversion(self):
        dept = Department.objects.create(faculty=self.faculty, name="Computer Science", code="csc")
        self.assertEqual(dept.code, "CSC")

    def test_duplicate_code_raises_integrity_error(self):
        Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC")
        with self.assertRaises((IntegrityError, ValidationError)):
            Department.objects.create(faculty=self.faculty, name="Cyber Security", code="CSC")

    def test_invalid_code_format_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            dept = Department(faculty=self.faculty, name="Test Dept", code="INVALID CODE!")
            dept.full_clean()

    def test_hierarchy_navigation(self):
        dept = Department.objects.create(faculty=self.faculty, name="Mathematics", code="MTH")
        self.assertEqual(dept.faculty.school.code, "NSUK")
        self.assertEqual(self.school.faculties.first().departments.count(), 1)
