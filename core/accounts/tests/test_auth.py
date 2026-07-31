from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import AdminOfficer, Student, User
from hierarchy.models import Department, Faculty, School


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="Federal University", code="FUD")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of Science", code="FSC")
        self.department = Department.objects.create(
            faculty=self.faculty, name="Computer Science", code="CSC"
        )

        # Create seeded user with initial default password
        self.user = User.objects.create_user(
            identifier="NSUK/CSC/2021/001",
            password="InitialPassword123",
            role=User.Role.STUDENT,
            requires_password_reset=True,
        )
        self.student = Student.objects.create(
            user=self.user,
            matric_number="NSUK/CSC/2021/001",
            full_name="John Doe",
            department=self.department,
            level=300,
        )

    def test_login_success_returns_jwt_and_reset_flag(self):
        url = reverse("auth_login")
        response = self.client.post(
            url,
            {"identifier": "NSUK/CSC/2021/001", "password": "InitialPassword123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertTrue(response.data["requires_password_reset"])
        self.assertEqual(response.data["user"]["identifier"], "NSUK/CSC/2021/001")

    def test_login_invalid_password_fails(self):
        url = reverse("auth_login")
        response = self.client.post(
            url,
            {"identifier": "NSUK/CSC/2021/001", "password": "WrongPassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("tokens", response.data)

    def test_forced_password_reset_flow(self):
        # 1. Login to get tokens
        login_url = reverse("auth_login")
        login_res = self.client.post(
            login_url,
            {"identifier": "NSUK/CSC/2021/001", "password": "InitialPassword123"},
            format="json",
        )
        access_token = login_res.data["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # 2. Access protected endpoint before reset should be blocked by IsPasswordResetDone
        profile_url = reverse("user_profile")
        profile_res = self.client.get(profile_url)
        self.assertEqual(profile_res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Perform password reset
        reset_url = reverse("auth_password_reset")
        reset_res = self.client.post(
            reset_url,
            {"new_password": "NewSecurePassword123"},
            format="json",
        )
        self.assertEqual(reset_res.status_code, status.HTTP_200_OK)

        # Verify user model is updated
        self.user.refresh_from_db()
        self.assertFalse(self.user.requires_password_reset)
        self.assertTrue(self.user.check_password("NewSecurePassword123"))

        # 4. Now accessing profile should succeed
        profile_res2 = self.client.get(profile_url)
        self.assertEqual(profile_res2.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res2.data["profile"]["full_name"], "John Doe")
