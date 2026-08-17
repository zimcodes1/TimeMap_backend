import pytest
from hierarchy.models import Department, Faculty, School
from accounts.models import Student, LecturerStaff, AdminOfficer, User
from accounts.serializers import StudentProfileSerializer, LecturerProfileSerializer, AdminProfileSerializer
from rest_framework.exceptions import ValidationError


@pytest.mark.django_db
class TestAccountValidations:
    @pytest.fixture(autouse=True)
    def setup_hierarchy(self):
        self.school = School.objects.create(name="Science School", code="SCI")
        self.faculty = Faculty.objects.create(school=self.school, name="Science Faculty", code="FSC")
        self.dept_csc = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC", max_level=400)
        self.dept_eee = Department.objects.create(faculty=self.faculty, name="Electrical Eng", code="EEE", max_level=500)

    def test_student_level_exceeding_max_level(self):
        data = {
            "matric_number": "CSC/2021/001",
            "full_name": "John Doe",
            "department": self.dept_csc.id,
            "level": 500,  # Exceeds max_level=400
            "email": "john@nsuk.edu.ng",
        }
        serializer = StudentProfileSerializer(data=data)
        assert not serializer.is_valid()
        assert "level" in serializer.errors

    def test_student_valid_level(self):
        data = {
            "matric_number": "CSC/2021/002",
            "full_name": "Jane Doe",
            "department": self.dept_csc.id,
            "level": 400,
            "email": "jane@nsuk.edu.ng",
        }
        serializer = StudentProfileSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_max_two_class_reps_per_dept_level(self):
        # Create rep 1
        s1_user = User.objects.create_user(identifier="REP1", role="student")
        Student.objects.create(user=s1_user, matric_number="REP1", full_name="Rep 1", department=self.dept_csc, level=300, is_class_rep=True)

        # Create rep 2
        s2_user = User.objects.create_user(identifier="REP2", role="student")
        Student.objects.create(user=s2_user, matric_number="REP2", full_name="Rep 2", department=self.dept_csc, level=300, is_class_rep=True)

        # Attempt to create rep 3 in same dept and level
        data = {
            "matric_number": "REP3",
            "full_name": "Rep 3",
            "department": self.dept_csc.id,
            "level": 300,
            "is_class_rep": True,
            "email": "rep3@nsuk.edu.ng",
        }
        serializer = StudentProfileSerializer(data=data)
        assert not serializer.is_valid()
        assert "is_class_rep" in serializer.errors

    def test_duplicate_email_across_roles(self):
        # Create student with email
        s_user = User.objects.create_user(identifier="STU100", role="student")
        Student.objects.create(user=s_user, matric_number="STU100", full_name="Student One", department=self.dept_csc, level=200, email="common@nsuk.edu.ng")

        # Attempt to create lecturer with same email
        data = {
            "staff_id": "LEC100",
            "full_name": "Lecturer One",
            "department": self.dept_csc.id,
            "email": "common@nsuk.edu.ng",
        }
        serializer = LecturerProfileSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors
