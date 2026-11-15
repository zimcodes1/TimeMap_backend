#!/usr/bin/env python3
"""
Production Database Migration Script: SQLite -> Neon PostgreSQL
Migrates all tables and records from db.sqlite3 to PostgreSQL on Neon in exact
topological foreign key order, resets all primary key sequences, and verifies data integrity.
"""
import sqlite3
import psycopg2
from psycopg2.extras import execute_values, Json
import os
import sys
import json
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SQLITE_PATH = BASE_DIR / "db.sqlite3"
POSTGRES_URL = os.getenv("DATABASE_URL")

if not POSTGRES_URL:
    print("ERROR: DATABASE_URL not set in .env")
    sys.exit(1)

if not SQLITE_PATH.exists():
    print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
    sys.exit(1)

# Topological order of tables based on foreign key dependencies
TABLES_ORDER = [
    "hierarchy_school",
    "hierarchy_faculty",
    "hierarchy_department",
    "hierarchy_program",
    "accounts_user",
    "accounts_adminofficer",
    "accounts_lecturerstaff",
    "accounts_student",
    "venues_facility",
    "venues_venue",
    "venues_venue_facilities",
    "student_counts_programstudentcount",
    "scheduling_academicsession",
    "scheduling_semester",
    "scheduling_generationscopepermission",
    "courses_course",
    "courses_course_lecturers",
    "courses_courseaccessgrant",
    "scheduling_timetableentry",
    "scheduling_lecturesession",
    "scheduling_timetablegenerationrun",
    "scheduling_examoptimizerrun",
    "reporting_classrepreport",
    "reporting_unreportedsessionflag",
    "notifications_devicetoken",
    "notifications_notification",
    "analytics_analyticsquerylog",
    "discrepancies_auditlog",
]


def transform_val(val, dt):
    if val is None:
        return None
    if dt == "boolean":
        return bool(val)
    if dt in ("jsonb", "json"):
        if isinstance(val, (dict, list)):
            return Json(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return None
            try:
                return Json(json.loads(s))
            except Exception:
                return Json(s)
        return Json(val)
    if dt == "uuid":
        if isinstance(val, str):
            return str(uuid.UUID(val))
    if dt in ("timestamp with time zone", "date", "time without time zone"):
        if isinstance(val, str) and not val.strip():
            return None
    return val


def run_migration():
    print("=" * 70)
    print("STARTING SQLITE TO NEON POSTGRESQL MIGRATION")
    print(f"Source: {SQLITE_PATH}")
    print(f"Target: {POSTGRES_URL.split('@')[-1]}")
    print("=" * 70)

    start_time = time.time()

    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_conn.autocommit = False
    pg_cur = pg_conn.cursor()

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cur = sqlite_conn.cursor()

    # Query Postgres column data types
    pg_cur.execute(
        """
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public';
    """
    )
    col_types = {(t, c): dt for t, c, dt in pg_cur.fetchall()}

    total_inserted = 0

    try:
        print("\n[Phase 1/3] Migrating table data in dependency order...")
        for table in TABLES_ORDER:
            sqlite_cur.execute(f'PRAGMA table_info("{table}");')
            cols = [r[1] for r in sqlite_cur.fetchall()]

            sqlite_cur.execute(f'SELECT {", ".join(cols)} FROM "{table}";')
            rows = sqlite_cur.fetchall()

            if not rows:
                print(f"  - {table}: 0 rows (skipped)")
                continue

            types = [col_types.get((table, c), "") for c in cols]

            transformed_rows = []
            for r in rows:
                transformed_rows.append(
                    tuple(transform_val(v, t) for v, t in zip(r, types))
                )

            insert_sql = f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES %s'
            execute_values(pg_cur, insert_sql, transformed_rows, page_size=5000)
            total_inserted += len(rows)
            print(f"  ✓ {table}: {len(rows):,} rows inserted")

        print("\nCommitting transaction...")
        pg_conn.commit()
        print(f"✓ All {total_inserted:,} rows committed successfully to PostgreSQL!")

        # Phase 2: Reset all sequences
        print("\n[Phase 2/3] Resetting PostgreSQL sequences...")
        pg_cur.execute(
            """
            SELECT 
                t.table_name,
                c.column_name,
                pg_get_serial_sequence(t.table_name, c.column_name) as seq_name
            FROM information_schema.tables t
            JOIN information_schema.columns c 
              ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            WHERE t.table_schema = 'public' 
              AND pg_get_serial_sequence(t.table_name, c.column_name) IS NOT NULL;
        """
        )
        sequences = pg_cur.fetchall()
        for table_name, col_name, seq_name in sequences:
            pg_cur.execute(
                f"""
                SELECT setval(%s, COALESCE((SELECT MAX("{col_name}") FROM "{table_name}"), 1));
            """,
                (seq_name,),
            )
        pg_conn.commit()
        print(f"✓ {len(sequences)} sequences reset to match maximum IDs.")

        # Phase 3: Verification
        print("\n[Phase 3/3] Verifying row counts across SQLite and PostgreSQL...")
        print(f"{'Table Name':<42} {'SQLite':>10} {'PostgreSQL':>12} {'Status':>8}")
        print("-" * 75)

        all_matched = True
        for table in TABLES_ORDER:
            sqlite_cur.execute(f'SELECT count(*) FROM "{table}";')
            s_count = sqlite_cur.fetchone()[0]

            pg_cur.execute(f'SELECT count(*) FROM "{table}";')
            p_count = pg_cur.fetchone()[0]

            status = "MATCH" if s_count == p_count else "MISMATCH"
            if status != "MATCH":
                all_matched = False
            print(f"{table:<42} {s_count:>10,} {p_count:>12,} {status:>8}")

        print("-" * 75)
        elapsed = time.time() - start_time
        if all_matched:
            print(f"\n🎉 MIGRATION 100% SUCCESSFUL! Completed in {elapsed:.1f}s.")
        else:
            print(f"\n⚠️ WARNING: Some row counts did not match! Check the log above.")

    except Exception as e:
        pg_conn.rollback()
        print(f"\n❌ ERROR during migration: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        pg_cur.close()
        pg_conn.close()
        sqlite_cur.close()
        sqlite_conn.close()


if __name__ == "__main__":
    run_migration()
