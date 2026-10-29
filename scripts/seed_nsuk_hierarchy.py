#!/usr/bin/env python3
"""
Standalone runner script to seed NSUK academic hierarchy (10 faculties, departments,
programs) and scope admin users.

Usage:
    cd TimeMap_backend
    uv run python scripts/seed_nsuk_hierarchy.py
    # or with custom default password:
    uv run python scripts/seed_nsuk_hierarchy.py --default-password "CustomAdmin#2026"
    # or reset existing scope admins:
    uv run python scripts/seed_nsuk_hierarchy.py --reset-existing-passwords
"""

import os
import sys
from pathlib import Path

# Setup Django environment
BACKEND_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BACKEND_DIR / "core"
sys.path.insert(0, str(CORE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.core.management import call_command


def main():
    args = sys.argv[1:]
    call_command("seed_nsuk_hierarchy", *args)


if __name__ == "__main__":
    main()

