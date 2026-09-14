from accounts.models import AdminOfficer, User
from hierarchy.models import Department, Faculty, Program, School
from rest_framework import status
from rest_framework.test import APITestCase


class ProgramTests(APITestCase):
    def setUp(self):
        self.school = School.objects.create(name="School of Computing", code="SOC")
        self.faculty = Faculty.objects.create(school=self.school, name="Faculty of IT", code="FIT")
        self.department = Department.objects.create(faculty=self.faculty, name="Computer Science", code="CSC", max_level=400)
        self.other_dept = Department.objects.create(faculty=self.faculty, name="Information Systems", code="IFS", max_level=400)

        # Department admin for Computer Science
        self.dept_admin_user = User.objects.create_user(
            identifier="ADM_CSC", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.dept_admin = AdminOfficer.objects.create(
            user=self.dept_admin_user, staff_id="ADM_CSC", full_name="CSC Admin",
            level=AdminOfficer.Level.DEPARTMENT, scope_department=self.department,
        )

        # Faculty admin
        self.fac_admin_user = User.objects.create_user(
            identifier="ADM_FAC", password="password", role=User.Role.ADMIN, requires_password_reset=False
        )
        self.fac_admin = AdminOfficer.objects.create(
            user=self.fac_admin_user, staff_id="ADM_FAC", full_name="Faculty Admin",
            level=AdminOfficer.Level.FACULTY, scope_faculty=self.faculty,
        )

    def test_default_program_auto_created_with_department(self):
        # When self.department was created, a default program should have been auto-created
        default_prog = Program.objects.filter(department=self.department, is_default=True).first()
        self.assertIsNotNone(default_prog)
        self.assertEqual(default_prog.name, self.department.name)
        self.assertEqual(default_prog.max_level, 400)
        self.assertTrue(default_prog.is_default)

    def test_dept_admin_can_create_and_manage_programs(self):
        self.client.force_authenticate(user=self.dept_admin_user)

        # Create Cyber Security program
        response = self.client.post(
            "/api/hierarchy/programs/",
            {
                "department": self.department.id,
                "name": "Cyber Security",
                "code": "CYB",
                "max_level": 500,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Cyber Security")
        self.assertEqual(response.data["code"], "CYB")
        self.assertEqual(response.data["max_level"], 500)
        self.assertFalse(response.data["is_default"])

        prog_id = response.data["id"]

        # Update the program
        update_res = self.client.patch(
            f"/api/hierarchy/programs/{prog_id}/",
            {"name": "Cybersecurity and Digital Forensics"},
            format="json",
        )
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data["name"], "Cybersecurity and Digital Forensics")

        # Dept admin cannot create program in another department
        denied_res = self.client.post(
            "/api/hierarchy/programs/",
            {
                "department": self.other_dept.id,
                "name": "Data Analytics",
                "code": "DAN",
                "max_level": 400,
            },
            format="json",
        )
        self.assertEqual(denied_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_program_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.dept_admin_user)
        default_prog = Program.objects.filter(department=self.department, is_default=True).first()

        delete_res = self.client.delete(f"/api/hierarchy/programs/{default_prog.id}/")
        self.assertEqual(delete_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Program.objects.filter(id=default_prog.id).exists())

    def test_higher_admin_viewership_bubbles_up(self):
        self.client.force_authenticate(user=self.fac_admin_user)

        # Faculty admin can view all programs under their faculty's departments
        res = self.client.get("/api/hierarchy/programs/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        prog_ids = [p["id"] for p in res.data]
        default_prog = Program.objects.filter(department=self.department, is_default=True).first()
        self.assertIn(default_prog.id, prog_ids)

        # But faculty admin cannot create programs (restricted to dept admins)
        create_res = self.client.post(
            "/api/hierarchy/programs/",
            {
                "department": self.department.id,
                "name": "Software Engineering",
                "code": "SEN",
                "max_level": 400,
            },
            format="json",
        )
        self.assertEqual(create_res.status_code, status.HTTP_403_FORBIDDEN)

