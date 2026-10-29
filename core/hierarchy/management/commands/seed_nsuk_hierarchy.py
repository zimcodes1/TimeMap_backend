"""
Django management command to seed comprehensive academic hierarchy and scope admin users
for Nasarawa State University Keffi (NSUK).

Sets up:
- 10 Faculties in total (FNAS, ADMIN, ARTS, FSS, LAW, AGRIC, EDU, ENV, ENG, FMHS)
- Relevant Departments across all faculties with appropriate max_levels
- Academic Programs under each department (default + specialized programs)
- Admin Officers and User accounts for every created scope (School, Faculty, and Department)
  configured with default password and requires_password_reset=True.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from accounts.models import AdminOfficer, User
from hierarchy.models import Department, Faculty, Program, School


class Command(BaseCommand):
    help = "Seed 10 faculties, relevant departments, programs, and scope admin users for NSUK."

    def add_arguments(self, parser):
        parser.add_argument(
            "--school-code",
            type=str,
            default="NSUK",
            help="School code (default: NSUK).",
        )
        parser.add_argument(
            "--default-password",
            type=str,
            default="Admin@123",
            help="Default password for newly created admin users (default: Admin@123).",
        )
        parser.add_argument(
            "--reset-existing-passwords",
            action="store_true",
            help="Reset passwords of existing scope admins back to the default password.",
        )

    def handle(self, *args, **options):
        school_code = options["school_code"].strip().upper()
        default_password = options["default_password"]
        reset_existing = options["reset_existing_passwords"]

        self.stdout.write(self.style.NOTICE(f"=== Starting NSUK Hierarchy & Admin Seeding ({school_code}) ==="))

        with transaction.atomic():
            # 1. Resolve or create School
            school, school_created = School.objects.get_or_create(
                code=school_code,
                defaults={"name": "Nasarawa State University Keffi"},
            )
            if school_created:
                self.stdout.write(self.style.SUCCESS(f"Created School: {school.name} ({school.code})"))
            else:
                self.stdout.write(f"Using existing School: {school.name} ({school.code})")

            # 2. Ensure School Scope Admin
            school_admin, s_user = self._ensure_school_admin(school, default_password, reset_existing)

            # 3. Hierarchy Specification (10 Faculties with relevant departments and programs)
            hierarchy_specs = self._get_hierarchy_specs()

            created_faculties = 0
            created_depts = 0
            created_progs = 0
            created_admins = 0
            all_scope_admins = []

            if school_admin:
                all_scope_admins.append({
                    "scope_type": "School",
                    "scope_name": school.name,
                    "scope_code": school.code,
                    "username": s_user.identifier,
                    "staff_id": school_admin.staff_id,
                    "full_name": school_admin.full_name,
                    "email": school_admin.email,
                    "level": school_admin.level,
                    "is_new": bool(school_created),
                })

            # 4. Iterate and Seed Faculties, Departments, Programs & Admins
            for fac_code, fac_data in hierarchy_specs.items():
                faculty, f_created = Faculty.objects.get_or_create(
                    school=school,
                    code=fac_code,
                    defaults={"name": fac_data["name"]},
                )
                if f_created:
                    created_faculties += 1
                    self.stdout.write(self.style.SUCCESS(f"  + Faculty created: {faculty.name} ({faculty.code})"))
                else:
                    self.stdout.write(f"  * Faculty exists: {faculty.name} ({faculty.code})")

                # Ensure Faculty Scope Admin
                fac_admin, fac_user, fa_new = self._ensure_faculty_admin(
                    faculty, default_password, reset_existing
                )
                if fa_new:
                    created_admins += 1
                all_scope_admins.append({
                    "scope_type": "Faculty",
                    "scope_name": faculty.name,
                    "scope_code": faculty.code,
                    "username": fac_user.identifier,
                    "staff_id": fac_admin.staff_id,
                    "full_name": fac_admin.full_name,
                    "email": fac_admin.email,
                    "level": fac_admin.level,
                    "is_new": fa_new,
                })

                # Seed Departments under this Faculty
                for dept_code, dept_data in fac_data["departments"].items():
                    dept, d_created = Department.objects.get_or_create(
                        code=dept_code,
                        defaults={
                            "faculty": faculty,
                            "name": dept_data["name"],
                            "max_level": dept_data.get("max_level", 400),
                        },
                    )
                    if d_created:
                        created_depts += 1
                        self.stdout.write(f"    + Dept created: {dept.name} ({dept.code}) [max: {dept.max_level}L]")
                    else:
                        # Ensure faculty relationship is correct
                        if dept.faculty_id != faculty.id:
                            dept.faculty = faculty
                            dept.save(update_fields=["faculty"])

                    # Seed Specialized Programs
                    dept_progs = dept_data.get("programs", [])
                    for prog_info in dept_progs:
                        prog_code = prog_info["code"]
                        prog_name = prog_info["name"]
                        prog_max = prog_info.get("max_level", dept.max_level)

                        prog, p_created = Program.objects.get_or_create(
                            department=dept,
                            code=prog_code,
                            defaults={
                                "name": prog_name,
                                "max_level": prog_max,
                                "is_default": False,
                            },
                        )
                        if p_created:
                            created_progs += 1
                            self.stdout.write(f"      - Program added: {prog.name} ({prog.code})")

                    # Ensure Department Scope Admin
                    dept_admin, dept_user, da_new = self._ensure_department_admin(
                        dept, default_password, reset_existing
                    )
                    if da_new:
                        created_admins += 1
                    all_scope_admins.append({
                        "scope_type": "Department",
                        "scope_name": dept.name,
                        "scope_code": dept.code,
                        "username": dept_user.identifier,
                        "staff_id": dept_admin.staff_id,
                        "full_name": dept_admin.full_name,
                        "email": dept_admin.email,
                        "level": dept_admin.level,
                        "is_new": da_new,
                    })

        # 5. Output Summary
        total_faculties = Faculty.objects.filter(school=school).count()
        total_depts = Department.objects.filter(faculty__school=school).count()
        total_progs = Program.objects.filter(department__faculty__school=school).count()

        self.stdout.write(self.style.SUCCESS("\n=== Seeding Finished Successfully! ==="))
        self.stdout.write(f"School: {school.name} ({school.code})")
        self.stdout.write(f"Total Faculties in NSUK: {total_faculties} (New: {created_faculties})")
        self.stdout.write(f"Total Departments in NSUK: {total_depts} (New: {created_depts})")
        self.stdout.write(f"Total Programs in NSUK: {total_progs} (New: {created_progs})")
        self.stdout.write(f"Total New Scope Admins Created: {created_admins}")
        self.stdout.write(f"Default Password for all seeded accounts: {default_password}")
        self.stdout.write("All accounts have requires_password_reset=True to prompt password update on first login.\n")

        self.stdout.write("=== Summary of Scope Admin Accounts ===")
        self.stdout.write(f"{'Scope':<12} | {'Code':<8} | {'Username/StaffID':<18} | {'Admin Name':<32} | {'Status'}")
        self.stdout.write("-" * 90)
        for adm in all_scope_admins:
            status_str = "CREATED (Needs Reset)" if adm["is_new"] else "EXISTING"
            self.stdout.write(
                f"{adm['scope_type']:<12} | {adm['scope_code']:<8} | {adm['username']:<18} | {adm['full_name'][:30]:<32} | {status_str}"
            )

    def _ensure_school_admin(self, school, default_password, reset_existing):
        admin = AdminOfficer.objects.filter(
            Q(scope_school=school) | Q(level=AdminOfficer.Level.SCHOOL)
        ).first()
        if admin:
            user = admin.user
            if reset_existing:
                user.set_password(default_password)
                user.requires_password_reset = True
                user.save(update_fields=["password", "requires_password_reset"])
            return admin, user

        staff_id = f"NSUK-ADM-SCH"
        user, _ = User.objects.get_or_create(
            identifier=staff_id,
            defaults={
                "role": User.Role.ADMIN,
                "requires_password_reset": True,
                "is_active": True,
                "is_staff": True,
            },
        )
        user.set_password(default_password)
        user.save()

        admin, _ = AdminOfficer.objects.get_or_create(
            user=user,
            defaults={
                "staff_id": staff_id,
                "full_name": f"{school.name} School Administrator",
                "level": AdminOfficer.Level.SCHOOL,
                "email": "admin.school@nsuk.edu.ng",
                "scope_school": school,
            },
        )
        return admin, user

    def _ensure_faculty_admin(self, faculty, default_password, reset_existing):
        admin = AdminOfficer.objects.filter(scope_faculty=faculty).first()
        if admin:
            user = admin.user
            if reset_existing:
                user.set_password(default_password)
                user.requires_password_reset = True
                user.save(update_fields=["password", "requires_password_reset"])
            return admin, user, False

        staff_id = f"NSUK-ADM-{faculty.code}"
        user, created = User.objects.get_or_create(
            identifier=staff_id,
            defaults={
                "role": User.Role.ADMIN,
                "requires_password_reset": True,
                "is_active": True,
                "is_staff": True,
            },
        )
        user.set_password(default_password)
        user.requires_password_reset = True
        user.save()

        admin, _ = AdminOfficer.objects.get_or_create(
            user=user,
            defaults={
                "staff_id": staff_id,
                "full_name": f"{faculty.name} Faculty Admin",
                "level": AdminOfficer.Level.FACULTY,
                "email": f"admin.{faculty.code.lower()}@nsuk.edu.ng",
                "scope_faculty": faculty,
            },
        )
        return admin, user, True

    def _ensure_department_admin(self, dept, default_password, reset_existing):
        admin = AdminOfficer.objects.filter(scope_department=dept).first()
        if admin:
            user = admin.user
            if reset_existing:
                user.set_password(default_password)
                user.requires_password_reset = True
                user.save(update_fields=["password", "requires_password_reset"])
            return admin, user, False

        staff_id = f"NSUK-ADM-{dept.code}"
        user, created = User.objects.get_or_create(
            identifier=staff_id,
            defaults={
                "role": User.Role.ADMIN,
                "requires_password_reset": True,
                "is_active": True,
                "is_staff": True,
            },
        )
        user.set_password(default_password)
        user.requires_password_reset = True
        user.save()

        admin, _ = AdminOfficer.objects.get_or_create(
            user=user,
            defaults={
                "staff_id": staff_id,
                "full_name": f"{dept.name} Department Admin",
                "level": AdminOfficer.Level.DEPARTMENT,
                "email": f"admin.{dept.code.lower()}@nsuk.edu.ng",
                "scope_department": dept,
            },
        )
        return admin, user, True

    def _get_hierarchy_specs(self):
        """
        Returns definition for exactly 10 Faculties, their respective Departments,
        and specialized programs.
        """
        return {
            # 1. Faculty of Natural and Applied Sciences (Existing FNAS)
            "FNAS": {
                "name": "Faculty Of Natural and Applied Sciences",
                "departments": {
                    "CMP": {
                        "name": "Computer Science",
                        "max_level": 400,
                        "programs": [
                            {"name": "Cybersecurity", "code": "CMPCYS", "max_level": 400},
                            {"name": "Software Engineering", "code": "CMPSWE", "max_level": 400},
                        ],
                    },
                    "SLT": {"name": "Science Lab Technology", "max_level": 400, "programs": []},
                    "STA": {"name": "Statistics", "max_level": 400, "programs": []},
                    "BCH": {"name": "Biochemistry", "max_level": 400, "programs": []},
                    "MCB": {"name": "Microbiology", "max_level": 400, "programs": []},
                    "ZOO": {"name": "Zoology", "max_level": 400, "programs": []},
                    "MTH": {"name": "Mathematics", "max_level": 400, "programs": []},
                    "PHY": {
                        "name": "Physics",
                        "max_level": 400,
                        "programs": [
                            {"name": "Physics with Electronics", "code": "PHYELX", "max_level": 400},
                        ],
                    },
                    "CHM": {
                        "name": "Chemistry",
                        "max_level": 400,
                        "programs": [
                            {"name": "Industrial Chemistry", "code": "CHMIND", "max_level": 400},
                            {"name": "Pure Chemistry", "code": "CHMPUR", "max_level": 400},
                        ],
                    },
                },
            },

            # 2. Faculty of Administration (Existing ADMIN)
            "ADMIN": {
                "name": "Faculty of Administration",
                "departments": {
                    "BAM": {
                        "name": "Business Administration",
                        "max_level": 400,
                        "programs": [
                            {"name": "Marketing", "code": "BAMMKT", "max_level": 400},
                        ],
                    },
                    "ACC": {
                        "name": "Accounting",
                        "max_level": 400,
                        "programs": [
                            {"name": "Taxation", "code": "ACCTAX", "max_level": 400},
                        ],
                    },
                    "PAD": {
                        "name": "Public Administration",
                        "max_level": 400,
                        "programs": [
                            {"name": "Local Government Administration", "code": "PADLGA", "max_level": 400},
                        ],
                    },
                    "BFN": {
                        "name": "Banking and Finance",
                        "max_level": 400,
                        "programs": [
                            {"name": "Insurance and Risk Management", "code": "BFNINS", "max_level": 400},
                        ],
                    },
                },
            },

            # 3. Faculty of Arts
            "ARTS": {
                "name": "Faculty of Arts",
                "departments": {
                    "ELS": {
                        "name": "English and Literary Studies",
                        "max_level": 400,
                        "programs": [
                            {"name": "Literature in English", "code": "ELSLIT", "max_level": 400},
                        ],
                    },
                    "HIS": {
                        "name": "History and International Studies",
                        "max_level": 400,
                        "programs": [
                            {"name": "Diplomatic Studies", "code": "HISDIP", "max_level": 400},
                        ],
                    },
                    "TMA": {
                        "name": "Theatre and Media Arts",
                        "max_level": 400,
                        "programs": [
                            {"name": "Film and Media Studies", "code": "TMAFLM", "max_level": 400},
                        ],
                    },
                    "LIN": {
                        "name": "Languages and Linguistics",
                        "max_level": 400,
                        "programs": [
                            {"name": "French", "code": "LINFRN", "max_level": 400},
                            {"name": "Arabic", "code": "LINARB", "max_level": 400},
                        ],
                    },
                    "PRS": {
                        "name": "Philosophy and Religious Studies",
                        "max_level": 400,
                        "programs": [
                            {"name": "Christian Religious Studies", "code": "PRSCRS", "max_level": 400},
                            {"name": "Islamic Religious Studies", "code": "PRSIRS", "max_level": 400},
                        ],
                    },
                },
            },

            # 4. Faculty of Social Sciences
            "FSS": {
                "name": "Faculty of Social Sciences",
                "departments": {
                    "ECO": {
                        "name": "Economics",
                        "max_level": 400,
                        "programs": [
                            {"name": "Development Economics", "code": "ECODEV", "max_level": 400},
                        ],
                    },
                    "POL": {
                        "name": "Political Science",
                        "max_level": 400,
                        "programs": [
                            {"name": "International Relations", "code": "POLINT", "max_level": 400},
                        ],
                    },
                    "SOC": {
                        "name": "Sociology",
                        "max_level": 400,
                        "programs": [
                            {"name": "Criminology and Security Studies", "code": "SOCCRM", "max_level": 400},
                        ],
                    },
                    "MAC": {
                        "name": "Mass Communication",
                        "max_level": 400,
                        "programs": [
                            {"name": "Broadcasting", "code": "MACBRD", "max_level": 400},
                            {"name": "Public Relations and Advertising", "code": "MACADV", "max_level": 400},
                        ],
                    },
                    "PSY": {
                        "name": "Psychology",
                        "max_level": 400,
                        "programs": [],
                    },
                },
            },

            # 5. Faculty of Law
            "LAW": {
                "name": "Faculty of Law",
                "departments": {
                    "PIL": {
                        "name": "Public and International Law",
                        "max_level": 500,
                        "programs": [
                            {"name": "Common and Islamic Law", "code": "PILISL", "max_level": 500},
                        ],
                    },
                    "PCL": {
                        "name": "Private and Commercial Law",
                        "max_level": 500,
                        "programs": [
                            {"name": "International Trade Law", "code": "PCLTRD", "max_level": 500},
                        ],
                    },
                },
            },

            # 6. Faculty of Agriculture
            "AGRIC": {
                "name": "Faculty of Agriculture",
                "departments": {
                    "AGR": {
                        "name": "Agronomy",
                        "max_level": 500,
                        "programs": [
                            {"name": "Soil Science", "code": "AGRSOIL", "max_level": 500},
                        ],
                    },
                    "ANS": {
                        "name": "Animal Science",
                        "max_level": 500,
                        "programs": [
                            {"name": "Pasture and Range Management", "code": "ANSPAS", "max_level": 500},
                        ],
                    },
                    "AEE": {
                        "name": "Agricultural Economics and Extension",
                        "max_level": 500,
                        "programs": [
                            {"name": "Agricultural Extension", "code": "AEEEXT", "max_level": 500},
                        ],
                    },
                    "FAQ": {
                        "name": "Fisheries and Aquaculture",
                        "max_level": 500,
                        "programs": [],
                    },
                    "FOR": {
                        "name": "Forestry and Wildlife Management",
                        "max_level": 500,
                        "programs": [],
                    },
                },
            },

            # 7. Faculty of Education
            "EDU": {
                "name": "Faculty of Education",
                "departments": {
                    "EDF": {
                        "name": "Educational Foundations",
                        "max_level": 400,
                        "programs": [
                            {"name": "Early Childhood Education", "code": "EDFECE", "max_level": 400},
                        ],
                    },
                    "STM": {
                        "name": "Science, Technology and Mathematics Education",
                        "max_level": 400,
                        "programs": [
                            {"name": "Chemistry Education", "code": "STMCHM", "max_level": 400},
                            {"name": "Physics Education", "code": "STMPHY", "max_level": 400},
                            {"name": "Mathematics Education", "code": "STMMTH", "max_level": 400},
                            {"name": "Computer Science Education", "code": "STMCMP", "max_level": 400},
                        ],
                    },
                    "ASE": {
                        "name": "Arts and Social Science Education",
                        "max_level": 400,
                        "programs": [
                            {"name": "Economics Education", "code": "ASEECO", "max_level": 400},
                            {"name": "Social Studies Education", "code": "ASESOC", "max_level": 400},
                        ],
                    },
                    "GAC": {
                        "name": "Guidance and Counselling",
                        "max_level": 400,
                        "programs": [],
                    },
                },
            },

            # 8. Faculty of Environmental Science
            "ENV": {
                "name": "Faculty of Environmental Science",
                "departments": {
                    "ARC": {
                        "name": "Architecture",
                        "max_level": 500,
                        "programs": [],
                    },
                    "GEO": {
                        "name": "Geography and Environmental Management",
                        "max_level": 400,
                        "programs": [
                            {"name": "Environmental Resource Management", "code": "GEOENV", "max_level": 400},
                        ],
                    },
                    "URP": {
                        "name": "Urban and Regional Planning",
                        "max_level": 500,
                        "programs": [],
                    },
                    "ESM": {
                        "name": "Estate Management",
                        "max_level": 500,
                        "programs": [],
                    },
                    "QTS": {
                        "name": "Quantity Surveying",
                        "max_level": 500,
                        "programs": [],
                    },
                },
            },

            # 9. Faculty of Engineering
            "ENG": {
                "name": "Faculty of Engineering",
                "departments": {
                    "CVE": {
                        "name": "Civil Engineering",
                        "max_level": 500,
                        "programs": [
                            {"name": "Water Resources Engineering", "code": "CVEWTR", "max_level": 500},
                        ],
                    },
                    "EEE": {
                        "name": "Electrical and Electronics Engineering",
                        "max_level": 500,
                        "programs": [
                            {"name": "Telecommunications Engineering", "code": "EEETEL", "max_level": 500},
                        ],
                    },
                    "MEE": {
                        "name": "Mechanical Engineering",
                        "max_level": 500,
                        "programs": [
                            {"name": "Automotive Engineering", "code": "MEEAUT", "max_level": 500},
                        ],
                    },
                    "CHE": {
                        "name": "Chemical Engineering",
                        "max_level": 500,
                        "programs": [],
                    },
                },
            },

            # 10. Faculty of Medical and Health Sciences
            "FMHS": {
                "name": "Faculty of Medical and Health Sciences",
                "departments": {
                    "MED": {
                        "name": "Medicine and Surgery",
                        "max_level": 600,
                        "programs": [],
                    },
                    "NUR": {
                        "name": "Nursing Science",
                        "max_level": 500,
                        "programs": [],
                    },
                    "MLS": {
                        "name": "Medical Laboratory Science",
                        "max_level": 500,
                        "programs": [],
                    },
                    "PBH": {
                        "name": "Public Health",
                        "max_level": 400,
                        "programs": [
                            {"name": "Community Health", "code": "PBHCOM", "max_level": 400},
                        ],
                    },
                },
            },
        }

