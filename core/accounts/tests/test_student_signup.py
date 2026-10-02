from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Student, User
from hierarchy.models import Department, Faculty, Program, School


class StudentSignupTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Federal University", code="FUD")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.department = Department.objects.create(
            faculty=self.faculty, name="Computer Science", code="CSC"
        )
        self.program = Program.objects.filter(department=self.department).first()
        if not self.program:
            self.program = Program.objects.create(
                department=self.department,
                name="B.Sc Computer Science",
                code="CSC",
                max_level=400,
                is_default=True,
            )

    def test_registration_options(self):
        url = reverse("auth_registration_options")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("faculties", response.data)
        self.assertIn("departments", response.data)
        self.assertIn("programs", response.data)
        self.assertTrue(any(f["code"] == "FSC" for f in response.data["faculties"]))
        self.assertTrue(any(d["code"] == "CSC" for d in response.data["departments"]))
        self.assertTrue(any(p["code"] == "CSCGEN" for p in response.data["programs"]))

    def test_student_signup_success(self):
        url = reverse("auth_student_signup")
        payload = {
            "matric_number": "NSUK/CSC/2023/001",
            "full_name": "Jane Doe",
            "email": "janedoe@example.com",
            "faculty": self.faculty.id,
            "department": self.department.id,
            "program": self.program.id,
            "level": 200,
            "password": "SecurePassword123",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertFalse(response.data["requires_password_reset"])
        self.assertEqual(response.data["user"]["identifier"], "NSUK/CSC/2023/001")
        self.assertEqual(response.data["profile"]["full_name"], "Jane Doe")
        self.assertEqual(response.data["profile"]["level"], 200)

        # Verify DB records
        user = User.objects.get(identifier="NSUK/CSC/2023/001")
        self.assertTrue(user.check_password("SecurePassword123"))
        self.assertFalse(user.requires_password_reset)
        self.assertEqual(user.role, User.Role.STUDENT)

        student = Student.objects.get(matric_number="NSUK/CSC/2023/001")
        self.assertEqual(student.user, user)
        self.assertEqual(student.program, self.program)

    def test_student_signup_duplicate_matric_fails(self):
        url = reverse("auth_student_signup")
        payload = {
            "matric_number": "NSUK/CSC/2023/001",
            "full_name": "Jane Doe",
            "email": "janedoe@example.com",
            "faculty": self.faculty.id,
            "department": self.department.id,
            "program": self.program.id,
            "level": 200,
            "password": "SecurePassword123",
        }
        res1 = self.client.post(url, payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Second attempt with same matric number
        payload2 = payload.copy()
        payload2["email"] = "different@example.com"
        res2 = self.client.post(url, payload2, format="json")
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("matric_number", res2.data)

    def test_student_signup_invalid_level_fails(self):
        url = reverse("auth_student_signup")
        payload = {
            "matric_number": "NSUK/CSC/2023/002",
            "full_name": "Alice Smith",
            "email": "alice@example.com",
            "faculty": self.faculty.id,
            "department": self.department.id,
            "program": self.program.id,
            "level": 700,  # Max level is 400
            "password": "SecurePassword123",
        }
        res = self.client.post(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("level", res.data)
