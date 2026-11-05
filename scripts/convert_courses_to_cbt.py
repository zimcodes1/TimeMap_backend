#!/usr/bin/env python3
"""Standalone script to convert seeded courses to CBT / Written exam settings.

Usage:
    cd TimeMap_backend
    uv run python scripts/convert_courses_to_cbt.py
    # or with venv:
    .venv/bin/python scripts/convert_courses_to_cbt.py [--dry-run] [--faculty FNAS] [--department CMP]
"""

import os
import sys
from pathlib import Path

# Set up Django environment
BACKEND_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BACKEND_DIR / "core"
sys.path.insert(0, str(CORE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.core.management import call_command


def main():
    args = sys.argv[1:]
    call_command("set_course_exam_settings", *args)


if __name__ == "__main__":
    main()

