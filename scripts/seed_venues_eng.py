#!/usr/bin/env python3
"""
Standalone runner script to seed venues for the Faculty of Engineering (ENG) at NSUK.

Usage:
    cd TimeMap_backend
    uv run python scripts/seed_venues_eng.py
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
    call_command("seed_venues_eng", *sys.argv[1:])


if __name__ == "__main__":
    main()

