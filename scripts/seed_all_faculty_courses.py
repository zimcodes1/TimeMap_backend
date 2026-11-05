#!/usr/bin/env python3
"""
Master runner script to seed courses and cross-departmental access grants for all 10 faculties
at Nasarawa State University, Keffi (NSUK) for the current active semester.

Order of execution:
1. Faculty of Natural and Applied Sciences (FNAS) - foundational science & computing courses
2. Faculty of Administration (ADMIN) - foundational management, accounting & economics courses
3. Faculty of Arts (ARTS) - languages, history, theatre arts, philosophy
4. Faculty of Social Sciences (FSS) - sociology, political science, mass comm, psychology
5. Faculty of Law (LAW) - private, commercial, public, and international law
6. Faculty of Agriculture (AGRIC) - agronomy, animal sci, agric econ, fisheries, food sci
7. Faculty of Education (EDU) - educational foundations, science/math ed, arts ed, guidance & counselling
8. Faculty of Environmental Science (ENV) - architecture, geography, urban planning, estate mgt, quantity surveying
9. Faculty of Engineering (ENG) - civil, electrical, mechanical, chemical engineering
10. Faculty of Medical and Health Sciences (FMHS) - medicine, nursing, medical lab sci, public health

Usage:
    cd TimeMap_backend
    uv run python scripts/seed_all_faculty_courses.py [--school-code NSUK]
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


FACULTY_COMMANDS = [
    ("seed_courses_fnas", "Faculty of Natural and Applied Sciences (FNAS)"),
    ("seed_courses_admin", "Faculty of Administration (ADMIN)"),
    ("seed_courses_arts", "Faculty of Arts (ARTS)"),
    ("seed_courses_fss", "Faculty of Social Sciences (FSS)"),
    ("seed_courses_law", "Faculty of Law (LAW)"),
    ("seed_courses_agric", "Faculty of Agriculture (AGRIC)"),
    ("seed_courses_edu", "Faculty of Education (EDU)"),
    ("seed_courses_env", "Faculty of Environmental Science (ENV)"),
    ("seed_courses_eng", "Faculty of Engineering (ENG)"),
    ("seed_courses_fmhs", "Faculty of Medical and Health Sciences (FMHS)"),
]


def main():
    parser = argparse.ArgumentParser(description="Seed courses for all 10 faculties at NSUK.")
    parser.add_argument("--school-code", type=str, default="NSUK", help="Target School Code (default: NSUK)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"STARTING COMPREHENSIVE COURSE SEEDING FOR SCHOOL: {args.school_code}")
    print("=" * 70)

    for idx, (cmd_name, fac_label) in enumerate(FACULTY_COMMANDS, start=1):
        print(f"\n[{idx}/10] Seeding {fac_label}...")
        try:
            call_command(cmd_name, school_code=args.school_code)
        except Exception as e:
            print(f"Error seeding {fac_label} ({cmd_name}): {e}", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 70)
    print(f"SUCCESS: ALL 10 FACULTIES SEEDED WITH REALISTIC, COMPLIANT COURSES & ACCESS GRANTS!")
    print("=" * 70)


if __name__ == "__main__":
    main()

