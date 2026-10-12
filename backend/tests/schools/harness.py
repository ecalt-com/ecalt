"""Disposable-Postgres harness for DB integration tests (TESTING.md §3, L3).

The database is built from tests/db/prelude.sql + tests/db/schema_baseline.sql
+ every migration after BASELINE_MIGRATION, and rebuilt only when one of those
files changes (a fingerprint is stored as the comment on schema public).

Safety: refuses any URL whose host isn't local (or the CI service) or whose
database isn't `ecalt_test`, and re-checks current_database() after connecting.
backend/.env points at production — nothing here ever reads it.
"""
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

BACKEND = Path(__file__).resolve().parents[2]
DB_DIR = BACKEND / "tests" / "db"
MIGRATIONS_DIR = BACKEND.parent / "migrations"

# Last migration already contained in schema_baseline.sql.
BASELINE_MIGRATION = 12

TEST_DB_NAME = "ecalt_test"
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "postgres", "ecalt-test-db"}


class UnsafeDatabaseURL(RuntimeError):
    pass


def guard_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.hostname not in _ALLOWED_HOSTS or parsed.path.lstrip("/") != TEST_DB_NAME:
        raise UnsafeDatabaseURL(
            f"Refusing to run DB tests against {parsed.hostname}/{parsed.path.lstrip('/')}: "
            f"TEST_DATABASE_URL must point at a local '{TEST_DB_NAME}' database."
        )


def connect(url: str, autocommit: bool = True):
    guard_url(url)
    conn = psycopg2.connect(url, connect_timeout=5, sslmode="disable")
    conn.autocommit = autocommit
    with conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        if cur.fetchone()[0] != TEST_DB_NAME:
            conn.close()
            raise UnsafeDatabaseURL("Connected database is not ecalt_test")
    return conn


def _migration_files() -> list[Path]:
    files = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        try:
            number = int(path.name.split("_", 1)[0])
        except ValueError:
            continue
        if number > BASELINE_MIGRATION:
            files.append(path)
    return files


def _sources() -> list[Path]:
    return [DB_DIR / "prelude.sql", DB_DIR / "schema_baseline.sql", *_migration_files()]


def fingerprint() -> str:
    digest = hashlib.sha256()
    for path in _sources():
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "ecalt-test:" + digest.hexdigest()[:16]


def build_database(url: str, force: bool = False) -> None:
    """(Re)build the schema when the baseline or migrations changed."""
    expected = fingerprint()
    conn = connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT obj_description('public'::regnamespace, 'pg_namespace')")
            if not force and cur.fetchone()[0] == expected:
                return
            cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
            cur.execute("CREATE SCHEMA public")
            for path in _sources():
                cur.execute(path.read_text(encoding="utf-8"))
                # The dump empties search_path; migrations expect the default.
                cur.execute("SET search_path TO public, extensions")
            cur.execute(f"COMMENT ON SCHEMA public IS '{expected}'")
    finally:
        conn.close()


def table_names(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        return [r[0] for r in cur.fetchall()]


def truncate_all(conn, tables: list[str]) -> None:
    if not tables:
        return
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE " + ", ".join(f'public."{t}"' for t in tables) + " RESTART IDENTITY CASCADE"
        )
