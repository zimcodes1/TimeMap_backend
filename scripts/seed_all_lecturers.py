#!/usr/bin/env python3
"""
Master runner script to seed realistic lecturers and course assignments across all 10 faculties
at Nasarawa State University, Keffi (NSUK).

Order of execution:
1. Faculty of Natural and Applied Sciences (FNAS) + University GSTs
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
    uv run python scripts/seed_all_lecturers.py [--school-code NSUK] [--default-password Lecturer#2026]
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


FACULTY_LECTURER_COMMANDS = [
    ("seed_lecturers_fnas", "Faculty of Natural and Applied Sciences (FNAS)"),
    ("seed_lecturers_admin", "Faculty of Administration (ADMIN)"),
    ("seed_lecturers_arts", "Faculty of Arts (ARTS)"),
    ("seed_lecturers_fss", "Faculty of Social Sciences (FSS)"),
    ("seed_lecturers_law", "Faculty of Law (LAW)"),
    ("seed_lecturers_agric", "Faculty of Agriculture (AGRIC)"),
    ("seed_lecturers_edu", "Faculty of Education (EDU)"),
    ("seed_lecturers_env", "Faculty of Environmental Science (ENV)"),
    ("seed_lecturers_eng", "Faculty of Engineering (ENG)"),
    ("seed_lecturers_fmhs", "Faculty of Medical and Health Sciences (FMHS)"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed lecturers and assign to courses across all faculties at NSUK.")
    parser.add_argument("--school-code", type=str, default="NSUK", help="Target School Code (default: NSUK)")
    parser.add_argument("--default-password", type=str, default="Lecturer#2026", help="Default password for created lecturers")
    args = parser.parse_args()

    print("=" * 70)
    print(f"STARTING COMPREHENSIVE LECTURER SEEDING FOR SCHOOL: {args.school_code}")
    print("=" * 70)

    for idx, (cmd_name, fac_label) in enumerate(FACULTY_LECTURER_COMMANDS, start=1):
        print(f"\n[{idx}/10] Seeding Lecturers & Course Assignments for {fac_label}...")
        try:
            call_command(cmd_name, school_code=args.school_code, default_password=args.default_password)
        except Exception as e:
            print(f"Error seeding lecturers for {fac_label} ({cmd_name}): {e}", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 70)
    print(f"SUCCESS: ALL 10 FACULTIES SEEDED WITH REALISTIC LECTURERS & COURSE ASSIGNMENTS!")
    print("=" * 70)


if __name__ == "__main__":
    main()

