"""Delete a terminated school's data now, or list what's left (SC-803).

The nightly scheduler job does this automatically once the grace period ends.
Use this for support cases (a school asks for early deletion in writing) and
to verify offboarding on dev.

    python scripts/purge_school.py <school_id>                 # show what remains
    python scripts/purge_school.py <school_id> --delete        # delete (grace period must have ended)
    python scripts/purge_school.py <school_id> --delete --ignore-grace   # delete now

Refuses any school that isn't terminated.
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import school_offboarding_service as off  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("school_id")
    ap.add_argument("--delete", action="store_true", help="delete the school's data")
    ap.add_argument("--ignore-grace", action="store_true", help="don't wait for the grace period")
    args = ap.parse_args()

    print("remaining:", json.dumps(off.remaining(args.school_id)))
    if not args.delete:
        return 0
    if not args.ignore_grace and args.school_id not in off.due_school_ids():
        print(f"not due: the school isn't terminated or its {off.grace_days()}-day grace period hasn't ended")
        return 1
    result = asyncio.run(off.purge_school(args.school_id))
    print("result:", json.dumps(result, default=str))
    return 0 if result["status"] in ("deleted", "already_deleted") else 1


if __name__ == "__main__":
    sys.exit(main())
