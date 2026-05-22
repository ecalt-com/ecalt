"""Test script — fire notifications directly to a user, bypassing the scheduler.

Bypasses daily cap and quiet-hours gate. Respects global channel kill-switches
(NOTIFICATIONS_EMAIL_ENABLED / NOTIFICATIONS_WHATSAPP_ENABLED) unless --force-channel.

By default, pulls real user data from the DB (actual streak, topics, journeys) so
messages are realistic. Use --no-real-context to use hardcoded defaults instead.

Usage:
    cd backend && source .venv/bin/activate

    # Send one type (auto-picks active channel)
    python scripts/test_notification.py --email you@example.com
    python scripts/test_notification.py --email you@example.com --type streak_at_risk
    python scripts/test_notification.py --email you@example.com --type cliffhanger_return --channel whatsapp

    # Preview copy without sending
    python scripts/test_notification.py --email you@example.com --type weekly_digest --preview

    # Preview ALL types without sending (generates copy for each, no sends)
    python scripts/test_notification.py --email you@example.com --all --preview

    # Send ALL types (use carefully — spammy)
    python scripts/test_notification.py --email you@example.com --all

    # Override context fields
    python scripts/test_notification.py --email you@example.com --type streak_at_risk \\
        --context '{"streak_days": 30}'

    # Override kill-switch for a disabled channel
    python scripts/test_notification.py --email you@example.com --channel email --force-channel

    # Inspect state
    python scripts/test_notification.py --status
    python scripts/test_notification.py --email you@example.com --user-state
    python scripts/test_notification.py --list-types
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import app.core.config  # noqa: F401 — loads Settings from .env before other imports

# ── Notification catalogue ────────────────────────────────────────────────────

TYPES_BY_GROUP: dict[str, list[str]] = {
    "Core": [
        "daily_spark",
        "re_engagement",
        "cliffhanger_return",
    ],
    "Streak": [
        "streak_at_risk",
        "streak_lost",
        "streak_milestone",
    ],
    "Progress": [
        "journey_almost_done",
        "mind_signature_nudge",
        "mind_signature_ready",
    ],
    "Discovery": [
        "connection_alert",
        "world_event_hook",
    ],
    "Digest": [
        "weekly_digest",
        "family_highlight",
    ],
}

NOTIFICATION_TYPES = [t for group in TYPES_BY_GROUP.values() for t in group]

# Fallback contexts used when real DB data is absent or --no-real-context is set
DEFAULT_CONTEXTS: dict[str, dict] = {
    "daily_spark":          {"topics": "physics, history", "angle": "physics"},
    "re_engagement":        {"domain": "physics", "days_inactive": 10},
    "cliffhanger_return":   {"topic": "quantum entanglement"},
    "streak_at_risk":       {"streak_days": 7},
    "streak_lost":          {"streak_days": 7},
    "streak_milestone":     {"streak_days": 7},
    "journey_almost_done":  {"journey_title": "How DNA Actually Works", "steps_remaining": 1},
    "mind_signature_nudge": {"domain": "physics", "mastery_pct": 42},
    "mind_signature_ready": {"domain": "biology"},
    "connection_alert":     {"topic_a": "music", "topic_b": "mathematics",
                             "connection": "frequency ratios underlie both harmony and prime distribution"},
    "world_event_hook":     {"event": "James Webb telescope new image", "topic": "astronomy"},
    "weekly_digest":        {"new_concepts": 8, "active_domains": 3,
                             "domains": "physics, history, music theory", "journeys_touched": 2},
    "family_highlight":     {"summary": "Your family explored 3 topics this week: DNA, climate, and the Renaissance."},
}


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_user_by_email(email: str):
    from app.core.database import get_db
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT uid, email, display_name FROM users WHERE email = %s", (email,))
            return cur.fetchone()


def get_real_context(uid: str) -> dict:
    """Pull live user data from DB so messages reflect real state, not hardcoded defaults."""
    from datetime import date
    from app.core.database import get_db

    ctx: dict = {}
    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                # Topics / domain
                cur.execute("SELECT topics FROM user_interests WHERE uid = %s", (uid,))
                row = cur.fetchone()
                if row and row["topics"]:
                    topics = list(row["topics"])
                    ctx["topics"] = ", ".join(topics[:3])
                    ctx["angle"]  = topics[0]
                    ctx["domain"] = topics[0]

                # Streak + inactivity
                cur.execute("SELECT streak_days, last_active_date FROM users WHERE uid = %s", (uid,))
                row = cur.fetchone()
                if row:
                    ctx["streak_days"] = int(row["streak_days"] or 0)
                    if row["last_active_date"]:
                        ctx["days_inactive"] = (date.today() - row["last_active_date"]).days

                # In-progress journey closest to completion
                cur.execute(
                    """
                    SELECT j.title,
                           jsonb_array_length(j.steps) - COUNT(up.step_id) AS remaining
                    FROM journeys j
                    LEFT JOIN user_progress up ON up.uid = %s AND up.journey_id = j.id
                    WHERE j.uid = %s AND j.steps IS NOT NULL
                    GROUP BY j.id, j.title, j.steps
                    HAVING COUNT(up.step_id) > 0
                       AND jsonb_array_length(j.steps) - COUNT(up.step_id) > 0
                    ORDER BY remaining ASC
                    LIMIT 1
                    """,
                    (uid, uid),
                )
                row = cur.fetchone()
                if row:
                    ctx["journey_title"]   = row["title"]
                    ctx["steps_remaining"] = int(row["remaining"])

                # Top domain mastery
                cur.execute(
                    """
                    SELECT domain, ROUND(mastery_level * 100) AS mastery_pct
                    FROM domain_mastery WHERE uid = %s
                    ORDER BY mastery_level DESC LIMIT 1
                    """,
                    (uid,),
                )
                row = cur.fetchone()
                if row:
                    ctx.setdefault("domain", row["domain"])
                    ctx["mastery_pct"] = int(row["mastery_pct"])

                # Weekly knowledge stats
                cur.execute(
                    """
                    SELECT
                        COUNT(DISTINCT concept)
                            FILTER (WHERE discovered_at >= now() - interval '7 days') AS new_concepts,
                        COUNT(DISTINCT domain)
                            FILTER (WHERE last_reinforced >= now() - interval '7 days') AS active_domains,
                        STRING_AGG(DISTINCT domain, ', ')
                            FILTER (WHERE last_reinforced >= now() - interval '7 days') AS domains
                    FROM knowledge_nodes WHERE uid = %s
                    """,
                    (uid,),
                )
                row = cur.fetchone()
                if row:
                    ctx["new_concepts"]   = int(row["new_concepts"] or 0)
                    ctx["active_domains"] = int(row["active_domains"] or 0)
                    ctx["domains"]        = row["domains"] or ctx.get("domain", "various topics")

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT journey_id) AS jt
                    FROM user_progress
                    WHERE uid = %s AND completed_at >= now() - interval '7 days'
                    """,
                    (uid,),
                )
                row = cur.fetchone()
                if row:
                    ctx["journeys_touched"] = int(row["jt"] or 0)

                # WhatsApp opt-in state
                cur.execute(
                    "SELECT whatsapp_phone, whatsapp_opted_in FROM notification_preferences WHERE uid = %s",
                    (uid,),
                )
                row = cur.fetchone()
                if row:
                    ctx["_whatsapp_phone"]    = row["whatsapp_phone"]
                    ctx["_whatsapp_opted_in"] = bool(row["whatsapp_opted_in"])

    except Exception as e:
        print(f"  ⚠  Could not fetch real context ({e}) — falling back to defaults.")

    return ctx


def print_user_state(uid: str, display_name: str, real_ctx: dict) -> None:
    print(f"\n── User state: {display_name} ──────────────────────────────")
    fields = [
        ("streak_days",     "Streak"),
        ("days_inactive",   "Days inactive"),
        ("domain",          "Top domain"),
        ("mastery_pct",     "Mastery %"),
        ("topics",          "Topics"),
        ("journey_title",   "Journey in progress"),
        ("steps_remaining", "Steps remaining"),
        ("new_concepts",    "New concepts (7d)"),
        ("active_domains",  "Active domains (7d)"),
        ("journeys_touched","Journeys touched (7d)"),
        ("_whatsapp_phone", "WhatsApp phone"),
        ("_whatsapp_opted_in","WhatsApp opted in"),
    ]
    for key, label in fields:
        if key in real_ctx:
            print(f"  {label:<24} {real_ctx[key]}")
    print()


# ── Channel helpers ───────────────────────────────────────────────────────────

def _channel_status() -> dict[str, bool]:
    from app.core.config import settings
    return {
        "email":    settings.NOTIFICATIONS_EMAIL_ENABLED,
        "whatsapp": settings.NOTIFICATIONS_WHATSAPP_ENABLED,
    }


def _active_channels() -> list[str]:
    return [ch for ch, on in _channel_status().items() if on]


def print_status() -> None:
    status = _channel_status()
    print("Channel status (from .env):")
    for ch, enabled in status.items():
        mark = "✓ enabled" if enabled else "✗ disabled"
        print(f"  {ch:<12} {mark}")
    active = _active_channels()
    print(f"\nActive: {', '.join(active) if active else 'none — all disabled'}")


# ── Core send ─────────────────────────────────────────────────────────────────

async def preview_copy(notification_type: str, context: dict) -> dict:
    from app.services.copy_generator import generate_copy
    return await generate_copy(notification_type, context)


async def send_direct(
    uid: str,
    email: str,
    notification_type: str,
    channel: str,
    context: dict,
    force_channel: bool = False,
    preview_only: bool = False,
) -> bool:
    from app.core.config import settings
    from app.services.copy_generator import generate_copy
    from app.services.email_service import send_email
    from app.services.whatsapp_service import send_whatsapp
    from app.services.notification_service import notification_service
    from app.core.database import get_db

    # Kill-switch check
    if channel == "email" and not settings.NOTIFICATIONS_EMAIL_ENABLED and not force_channel:
        print("  ✗ Email disabled (NOTIFICATIONS_EMAIL_ENABLED=false). Use --force-channel to override.")
        return False
    if channel == "whatsapp" and not settings.NOTIFICATIONS_WHATSAPP_ENABLED and not force_channel:
        print("  ✗ WhatsApp disabled (NOTIFICATIONS_WHATSAPP_ENABLED=false). Use --force-channel to override.")
        return False

    print(f"  → Generating copy ...")
    copy = await generate_copy(notification_type, context)

    print(f"  Subject      : {copy['subject']}")
    print(f"  Short message: {copy['short_message']}")
    print(f"  HTML body    :\n    {copy['body_html'][:300].strip()} {'...' if len(copy['body_html']) > 300 else ''}")

    if preview_only:
        return True  # success = copy generated, no send

    success = False
    if channel == "email":
        print(f"\n  → Sending email to {email} ...")
        success = await send_email(
            to=email,
            subject=copy["subject"],
            html_body=copy["body_html"],
            text_body=copy["short_message"],
            uid=uid,
        )
    elif channel == "whatsapp":
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT whatsapp_phone, whatsapp_opted_in FROM notification_preferences WHERE uid = %s",
                    (uid,),
                )
                pref = cur.fetchone()
        if not pref or not pref["whatsapp_opted_in"] or not pref["whatsapp_phone"]:
            print("  ✗ User not opted in to WhatsApp (run opt-in flow in app first).")
            return False
        print(f"\n  → Sending WhatsApp to {pref['whatsapp_phone']} ...")
        success = await send_whatsapp(to_e164=pref["whatsapp_phone"], message=copy["short_message"])
    else:
        print(f"  ✗ Unknown channel: {channel}")
        return False

    if success:
        await notification_service.log_notification(
            uid, notification_type, channel,
            copy.get("subject"), copy.get("short_message"),
        )

    return success


# ── CLI ───────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test ECALT notifications for a specific user.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email",  help="Target user email address")
    parser.add_argument("--type",   dest="notification_type", default="daily_spark",
                        help="Notification type (default: daily_spark)")
    parser.add_argument("--channel", choices=["email", "whatsapp"],
                        help="Delivery channel. Defaults to first enabled channel in .env.")
    parser.add_argument("--context", default=None,
                        help="JSON string merged on top of real/default context (highest priority).")
    parser.add_argument("--force-channel", action="store_true",
                        help="Send even if the channel is disabled in .env.")
    parser.add_argument("--preview", action="store_true",
                        help="Generate and print copy without actually sending.")
    parser.add_argument("--all", dest="run_all", action="store_true",
                        help="Run every notification type. Combine with --preview to skip sending.")
    parser.add_argument("--no-real-context", action="store_true",
                        help="Use hardcoded default contexts instead of live DB data.")
    parser.add_argument("--status", action="store_true",
                        help="Show channel enable/disable status and exit.")
    parser.add_argument("--user-state", action="store_true",
                        help="Show the real DB state for --email and exit.")
    parser.add_argument("--list-types", action="store_true",
                        help="List all notification types grouped by category and exit.")
    args = parser.parse_args()

    # ── Info-only flags ───────────────────────────────────────────────────────

    if args.status:
        print_status()
        return 0

    if args.list_types:
        for group, types in TYPES_BY_GROUP.items():
            print(f"\n{group}:")
            for t in types:
                ctx_str = json.dumps(DEFAULT_CONTEXTS.get(t, {}))
                print(f"  {t:<26} {ctx_str}")
        return 0

    if not args.email:
        parser.error("--email is required (or use --status / --list-types)")

    user = get_user_by_email(args.email)
    if not user:
        print(f"✗ No user found with email '{args.email}'. Have they signed in at least once?")
        return 1

    uid          = str(user["uid"])
    display_name = user["display_name"] or args.email

    # Fetch real context once (shared across all types in --all mode)
    real_ctx = {} if args.no_real_context else get_real_context(uid)

    if args.user_state:
        print_user_state(uid, display_name, real_ctx)
        return 0

    # Resolve channel
    channel = args.channel
    if not channel:
        active = _active_channels()
        if not active:
            print("✗ All channels disabled in .env. Enable at least one and retry.")
            return 1
        channel = active[0]

    # Parse --context override
    extra_ctx: dict = {}
    if args.context:
        try:
            extra_ctx = json.loads(args.context)
        except json.JSONDecodeError as e:
            print(f"✗ --context is not valid JSON: {e}")
            return 1

    print_status()
    print(f"\n✓ User: {display_name} (uid={uid})")
    if args.preview:
        print("  Mode: PREVIEW — copy generated, nothing sent\n")
    print(f"  Channel: {channel}")
    print()

    # ── Single type ───────────────────────────────────────────────────────────

    if not args.run_all:
        if args.notification_type not in NOTIFICATION_TYPES:
            print(f"✗ Unknown type '{args.notification_type}'. Use --list-types.")
            return 1

        context = {
            "name": display_name,
            **DEFAULT_CONTEXTS.get(args.notification_type, {}),
            **real_ctx,
            **extra_ctx,
        }

        print(f"── {args.notification_type} {'(preview)' if args.preview else ''} ──")
        success = await send_direct(
            uid=uid, email=args.email,
            notification_type=args.notification_type,
            channel=channel, context=context,
            force_channel=args.force_channel,
            preview_only=args.preview,
        )
        verb = "Previewed" if args.preview else "Sent"
        print(f"\n{'✓' if success else '✗'} {verb} {'successfully' if success else 'failed'}.")
        return 0 if success else 1

    # ── All types ─────────────────────────────────────────────────────────────

    results: list[tuple[str, bool]] = []
    for group, types in TYPES_BY_GROUP.items():
        print(f"── {group} ──────────────────────────────────────────────")
        for notif_type in types:
            context = {
                "name": display_name,
                **DEFAULT_CONTEXTS.get(notif_type, {}),
                **real_ctx,
                **extra_ctx,
            }
            print(f"\n[{notif_type}]")
            try:
                ok = await send_direct(
                    uid=uid, email=args.email,
                    notification_type=notif_type,
                    channel=channel, context=context,
                    force_channel=args.force_channel,
                    preview_only=args.preview,
                )
            except Exception as e:
                print(f"  ✗ Exception: {e}")
                ok = False
            results.append((notif_type, ok))
            if not args.preview:
                await asyncio.sleep(1)  # avoid rate-limiting on rapid sends
        print()

    # Summary table
    verb = "Previewed" if args.preview else "Sent"
    passed = [t for t, ok in results if ok]
    failed = [t for t, ok in results if not ok]
    print(f"── Summary ({verb}) ──────────────────────────────────────────")
    print(f"  ✓ {len(passed)}/{len(results)} succeeded")
    if failed:
        print(f"  ✗ Failed: {', '.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
