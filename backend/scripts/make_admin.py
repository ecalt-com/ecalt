#!/usr/bin/env python3
"""
Promote or demote a user's admin status.

Usage:
  python scripts/make_admin.py --email user@example.com
  python scripts/make_admin.py --uid <firebase_uid>
  python scripts/make_admin.py --email user@example.com --revoke

Requires: DATABASE_URL set in environment (or .env in backend/).
Run from the backend/ directory so .env is loaded automatically.
"""
import argparse
import os
import sys

# Load .env from backend/ directory
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv optional if DATABASE_URL already in env

import psycopg2
import psycopg2.extras


def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set. Add it to backend/.env or export it.", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def main():
    parser = argparse.ArgumentParser(description="Manage admin users for ECALT")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="User's email address")
    group.add_argument("--uid", help="Firebase UID")
    parser.add_argument("--revoke", action="store_true", help="Revoke admin instead of granting")
    args = parser.parse_args()

    target_value = args.flag = args.email or args.uid
    target_col = "email" if args.email else "uid"
    new_state = not args.revoke
    action = "Revoking" if args.revoke else "Granting"

    conn = get_conn()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET is_admin = %s WHERE {target_col} = %s "
                "RETURNING uid, email, display_name, is_admin",
                (new_state, target_value),
            )
            row = cur.fetchone()
            if not row:
                print(f"ERROR: No user found with {target_col}={target_value!r}.", file=sys.stderr)
                print("The user must have signed in at least once.", file=sys.stderr)
                sys.exit(1)

            status = "ADMIN" if row["is_admin"] else "regular user"
            print(f"{action} admin for: {row['display_name']} <{row['email']}> ({row['uid']})")
            print(f"New status: {status}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
