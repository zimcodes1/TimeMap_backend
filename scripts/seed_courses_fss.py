#!/usr/bin/env python3
"""
Standalone runner script to seed courses and access grants for the Faculty of Social Sciences (FSS) at NSUK.

Usage:
    cd TimeMap_backend
    uv run python scripts/seed_courses_fss.py
"""

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


def main():
    call_command("seed_courses_fss", *sys.argv[1:])


if __name__ == "__main__":
    main()

