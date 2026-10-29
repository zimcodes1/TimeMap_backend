#!/usr/bin/env python3
"""
Master runner script to seed realistic student planning populations (ProgramStudentCount)
for all degree programs across all 10 faculties at Nasarawa State University, Keffi (NSUK).

Order of execution:
1. Faculty of Natural and Applied Sciences (FNAS)
2. Faculty of Administration (ADMIN)
3. Faculty of Arts (ARTS)
4. Faculty of Social Sciences (FSS)
5. Faculty of Law (LAW)
6. Faculty of Agriculture (AGRIC)
7. Faculty of Education (EDU)
8. Faculty of Environmental Science (ENV)
9. Faculty of Engineering (ENG)
10. Faculty of Medical and Health Sciences (FMHS)

Usage:
    cd TimeMap_backend
    uv run python scripts/seed_all_student_populations.py [--school-code NSUK]
"""

import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BACKEND_DIR / "core"
sys.path.insert(0, str(CORE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.core.management import call_command


FACULTY_POPULATION_COMMANDS = [
    ("seed_students_fnas", "Faculty of Natural and Applied Sciences (FNAS)"),
    ("seed_students_admin", "Faculty of Administration (ADMIN)"),
    ("seed_students_arts", "Faculty of Arts (ARTS)"),
    ("seed_students_fss", "Faculty of Social Sciences (FSS)"),
    ("seed_students_law", "Faculty of Law (LAW)"),
    ("seed_students_agric", "Faculty of Agriculture (AGRIC)"),
    ("seed_students_edu", "Faculty of Education (EDU)"),
    ("seed_students_env", "Faculty of Environmental Science (ENV)"),
    ("seed_students_eng", "Faculty of Engineering (ENG)"),
    ("seed_students_fmhs", "Faculty of Medical and Health Sciences (FMHS)"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed student populations for all degree programs at NSUK.")
    parser.add_argument("--school-code", type=str, default="NSUK", help="Target School Code (default: NSUK)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"STARTING COMPREHENSIVE STUDENT POPULATION SEEDING FOR: {args.school_code}")
    print("=" * 70)

    for idx, (cmd_name, fac_label) in enumerate(FACULTY_POPULATION_COMMANDS, start=1):
        print(f"\n[{idx}/10] Seeding Student Populations for {fac_label}...")
        try:
            call_command(cmd_name, school_code=args.school_code)
        except Exception as e:
            print(f"Error seeding student populations for {fac_label} ({cmd_name}): {e}", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 70)
    print(f"SUCCESS: ALL 10 FACULTIES SEEDED WITH REALISTIC STUDENT PLANNING POPULATIONS!")
    print("=" * 70)


if __name__ == "__main__":
    main()

