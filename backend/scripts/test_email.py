"""
Live SMTP delivery test — actually sends emails via the configured SMTP server.

Usage:
    python scripts/test_email.py                          # sends to SMTP_FROM_EMAIL
    python scripts/test_email.py --to you@example.com    # sends to a specific address
    python scripts/test_email.py --type coppa            # test the COPPA consent email
    python scripts/test_email.py --type all              # run all scenarios
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from the repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.email_service import send_email, send_parental_consent_email


def _check_config() -> bool:
    missing = [k for k in ("SMTP_HOST", "SMTP_LOGIN", "SMTP_PASSWORD") if not getattr(settings, k)]
    if missing:
        print(f"[FAIL] Missing config: {', '.join(missing)}")
        print("       Set them in .env and re-run.")
        return False
    print(f"[OK]  SMTP config loaded — host={settings.SMTP_HOST}:{settings.SMTP_PORT} login={settings.SMTP_LOGIN}")
    return True


async def test_basic(to: str) -> bool:
    print(f"\n--- Test: basic transactional email → {to}")
    ok = await send_email(
        to=to,
        subject="[ECALT] SMTP delivery test",
        html_body=(
            "<p style='font-family:sans-serif'>"
            "This is a <strong>live delivery test</strong> from ECALT's SMTP service.<br>"
            "If you received this, the Brevo SMTP integration is working correctly."
            "</p>"
        ),
        text_body=(
            "This is a live delivery test from ECALT's SMTP service.\n"
            "If you received this, the Brevo SMTP integration is working correctly."
        ),
        uid="smtp-test-uid-001",
        log_id="test-log-id-001",
    )
    status = "[OK]  Sent" if ok else "[FAIL] Send returned False — check logs above"
    print(status)
    return ok


async def test_coppa(to: str) -> bool:
    print(f"\n--- Test: COPPA parental consent email → {to}")
    ok = await send_parental_consent_email(
        parent_email=to,
        uid="smtp-test-uid-coppa",
        token="test-token-not-real",
    )
    status = "[OK]  Sent" if ok else "[FAIL] Send returned False — check logs above"
    print(status)
    return ok


async def test_missing_config() -> bool:
    print("\n--- Test: graceful skip when SMTP_HOST is empty")
    original_host = settings.SMTP_HOST
    settings.SMTP_HOST = ""
    ok = await send_email(
        to="nobody@example.com",
        subject="should not send",
        html_body="<p>test</p>",
        text_body="test",
        uid="test-uid-noconfig",
    )
    settings.SMTP_HOST = original_host
    passed = ok is False
    print("[OK]  Correctly skipped (returned False)" if passed else "[FAIL] Should have returned False")
    return passed


async def main():
    parser = argparse.ArgumentParser(description="Live SMTP delivery test")
    parser.add_argument("--to", default=settings.SMTP_FROM_EMAIL, help="Recipient address")
    parser.add_argument(
        "--type",
        choices=["basic", "coppa", "config", "all"],
        default="all",
        help="Which test to run (default: all)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ECALT SMTP delivery test")
    print("=" * 60)

    if not _check_config():
        sys.exit(1)

    results = []

    if args.type in ("basic", "all"):
        results.append(await test_basic(args.to))

    if args.type in ("coppa", "all"):
        results.append(await test_coppa(args.to))

    if args.type in ("config", "all"):
        results.append(await test_missing_config())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    if passed == total:
        print("All tests passed. Check your inbox at:", args.to)
    else:
        print("Some tests failed — review the output above.")
    print("=" * 60)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
