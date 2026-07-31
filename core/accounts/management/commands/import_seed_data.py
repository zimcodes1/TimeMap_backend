import csv
import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import AdminOfficer, LecturerStaff, Student, User
from hierarchy.models import Department, Faculty, School


def get_default_password(identifier, prefix="Pass"):
    clean_id = "".join(c for c in identifier if c.isalnum())
    suffix = clean_id[-4:] if len(clean_id) >= 4 else "1234"
    return f"{prefix}#{suffix}"


class Command(BaseCommand):
    help = "Seed database users (Students, Lecturers, Admin Officers) from CSV files."

    def add_arguments(self, parser):
        parser.add_argument("--students-csv", type=str, help="Path to students CSV file")
        parser.add_argument("--staff-csv", type=str, help="Path to staff CSV file")

    def handle(self, *args, **options):
        students_csv = options.get("students_csv")
        staff_csv = options.get("staff_csv")

        if not students_csv and not staff_csv:
            self.stdout.write(self.style.WARNING("No CSV files provided. Use --students-csv or --staff-csv."))
            return

        if students_csv:
            self.import_students(students_csv)

        if staff_csv:
            self.import_staff(staff_csv)

    @transaction.atomic
    def import_students(self, filepath):
        if not os.path.exists(filepath):
            raise CommandError(f"Students CSV file not found: {filepath}")

        self.stdout.write(f"Importing students from {filepath}...")
        created_count = 0
        updated_count = 0

        with open(filepath, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                matric_number = row["matric_number"].strip().upper()
                full_name = row["full_name"].strip()
                dept_code = row["department_code"].strip().upper()
                level = int(row["level"])
                is_class_rep = str(row.get("is_class_rep") or "false").lower() in ["true", "1", "yes"]
                email = (row.get("email") or "").strip() or None

                department = Department.objects.filter(code=dept_code).first()
                if not department:
                    self.stdout.write(
                        self.style.ERROR(f"Department code '{dept_code}' not found for student {matric_number}. Skipping.")
                    )
                    continue

                user, created = User.objects.get_or_create(
                    identifier=matric_number,
                    defaults={
                        "role": User.Role.STUDENT,
                        "requires_password_reset": True,
                        "is_active": True,
                    },
                )

                default_pass = get_default_password(matric_number, prefix="Pass")
                if created:
                    user.set_password(default_pass)
                    user.save()
                    created_count += 1
                else:
                    updated_count += 1

                Student.objects.update_or_create(
                    user=user,
                    defaults={
                        "matric_number": matric_number,
                        "full_name": full_name,
                        "department": department,
                        "level": level,
                        "is_class_rep": is_class_rep,
                        "email": email,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed students. Created: {created_count}, Updated: {updated_count}")
        )

    @transaction.atomic
    def import_staff(self, filepath):
        if not os.path.exists(filepath):
            raise CommandError(f"Staff CSV file not found: {filepath}")

        self.stdout.write(f"Importing staff from {filepath}...")
        created_count = 0
        updated_count = 0

        with open(filepath, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                staff_id = row["staff_id"].strip().upper()
                full_name = row["full_name"].strip()
                role_type = (row.get("role") or "lecturer").strip().lower()
                dept_code = (row.get("department_code") or "").strip().upper()
                email = (row.get("email") or "").strip() or None

                department = Department.objects.filter(code=dept_code).first() if dept_code else None

                user_role = User.Role.ADMIN if role_type == "admin" else User.Role.LECTURER
                user, created = User.objects.get_or_create(
                    identifier=staff_id,
                    defaults={
                        "role": user_role,
                        "requires_password_reset": True,
                        "is_active": True,
                    },
                )

                default_pass = get_default_password(staff_id, prefix="Staff")
                if created:
                    user.set_password(default_pass)
                    user.save()
                    created_count += 1
                else:
                    updated_count += 1

                if user_role == User.Role.LECTURER:
                    if not department:
                        self.stdout.write(
                            self.style.ERROR(f"Department '{dept_code}' required for lecturer {staff_id}. Skipping.")
                        )
                        continue
                    LecturerStaff.objects.update_or_create(
                        user=user,
                        defaults={
                            "staff_id": staff_id,
                            "full_name": full_name,
                            "department": department,
                            "email": email,
                        },
                    )
                elif user_role == User.Role.ADMIN:
                    admin_level = (row.get("admin_level") or "department").strip().lower()
                    faculty_code = (row.get("faculty_code") or "").strip().upper()
                    school_code = (row.get("school_code") or "").strip().upper()

                    scope_dept = department if admin_level == "department" else None
                    scope_fac = Faculty.objects.filter(code=faculty_code).first() if admin_level == "faculty" else None
                    scope_sch = School.objects.filter(code=school_code).first() if admin_level == "school" else None

                    AdminOfficer.objects.update_or_create(
                        user=user,
                        defaults={
                            "staff_id": staff_id,
                            "full_name": full_name,
                            "level": admin_level,
                            "scope_department": scope_dept,
                            "scope_faculty": scope_fac,
                            "scope_school": scope_sch,
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed staff. Created: {created_count}, Updated: {updated_count}")
        )
