"""Apply SQL migrations under backend/migrations/ to Supabase.

Reads credentials from backend/.env (DATABASE_URL preferred; falls back to
DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD).

Tracks applied files in a `schema_migrations` table so the script is idempotent
and safe to re-run. Each .sql file is executed inside a single transaction.

Usage:
    cd backend
    source .venv/bin/activate
    python scripts/run_migrations.py                # apply all pending
    python scripts/run_migrations.py --dry-run      # list pending without running
    python scripts/run_migrations.py --file add_notification_preferences.sql   # one file
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "migrations"


def connect():
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL", "").strip()
    common = dict(connect_timeout=10, sslmode="require")
    if url:
        return psycopg2.connect(url, **common)
    host = os.getenv("DB_HOST", "").strip()
    if not host:
        sys.exit("No DATABASE_URL or DB_HOST in .env — cannot connect.")
    return psycopg2.connect(
        host=host,
        port=int(os.getenv("DB_PORT", "5432") or 5432),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        **common,
    )


def ensure_tracking_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename    TEXT PRIMARY KEY,
                applied_at  TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    conn.commit()


def applied_set(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        return {r[0] for r in cur.fetchall()}


def apply_file(conn, path: Path) -> None:
    sql = path.read_text()
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
            (path.name,),
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="List pending migrations without applying.")
    parser.add_argument("--file", help="Apply a single migration by filename (relative to migrations/).")
    parser.add_argument("--force", action="store_true", help="Re-run a migration even if already recorded (use with --file).")
    args = parser.parse_args()

    if not MIGRATIONS_DIR.is_dir():
        sys.exit(f"Migrations directory not found: {MIGRATIONS_DIR}")

    all_files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    if not all_files:
        print("No .sql files in migrations/")
        return 0

    conn = connect()
    try:
        ensure_tracking_table(conn)
        already = applied_set(conn)

        if args.file:
            target = MIGRATIONS_DIR / args.file
            if not target.exists():
                sys.exit(f"File not found: {target}")
            if target.name in already and not args.force:
                print(f"[skip] {target.name} already applied (use --force to re-run)")
                return 0
            pending = [target]
        else:
            pending = [p for p in all_files if p.name not in already]

        if not pending:
            print(f"Up to date — {len(already)} migration(s) applied, 0 pending.")
            return 0

        print(f"Pending migrations ({len(pending)}):")
        for p in pending:
            print(f"  - {p.name}")

        if args.dry_run:
            print("\n(dry run — nothing applied)")
            return 0

        for p in pending:
            print(f"\n→ applying {p.name} ...")
            try:
                apply_file(conn, p)
                print(f"  ✓ done")
            except Exception as e:  # noqa: BLE001
                conn.rollback()
                print(f"  ✗ FAILED: {e}")
                return 2

        print(f"\nAll migrations applied successfully.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
