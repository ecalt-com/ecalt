import secrets
import string
from datetime import datetime, timezone, timedelta

from app.core.database import get_db


def apply_coupon(uid: str, code: str) -> dict:
    """
    Apply a coupon to a user. Returns a result dict.
    Raises ValueError with a user-facing message on any validation failure.
    """
    code = code.strip().upper()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM coupons WHERE code = %s", (code,))
            coupon = cur.fetchone()

    if not coupon:
        raise ValueError("Coupon not found.")
    if not coupon["is_active"]:
        raise ValueError("This coupon is no longer active.")
    if coupon["expires_at"] and coupon["expires_at"] < datetime.now(timezone.utc):
        raise ValueError("This coupon has expired.")
    if coupon["max_redemptions"] is not None and coupon["redemption_count"] >= coupon["max_redemptions"]:
        raise ValueError("This coupon has reached its maximum number of uses.")

    # Check if user already redeemed this coupon
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM coupon_redemptions WHERE uid = %s AND coupon_code = %s",
                (uid, code),
            )
            if cur.fetchone():
                raise ValueError("You have already used this coupon.")

    credit_expires_at = None
    if coupon["duration_days"]:
        credit_expires_at = datetime.now(timezone.utc) + timedelta(days=coupon["duration_days"])

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coupon_redemptions
                  (uid, coupon_code, credit_applied_cents, bonus_messages_applied, credit_expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    uid, code,
                    coupon["credit_cents"],
                    coupon["bonus_messages"],
                    credit_expires_at,
                ),
            )
            cur.execute(
                "UPDATE coupons SET redemption_count = redemption_count + 1 WHERE code = %s",
                (code,),
            )

    return {
        "code": code,
        "description": coupon["description"],
        "credit_cents": coupon["credit_cents"],
        "bonus_messages": coupon["bonus_messages"],
        "plan_override": coupon["plan_override"],
        "credit_expires_at": credit_expires_at.isoformat() if credit_expires_at else None,
    }


def create_coupon(
    code: str,
    description: str,
    credit_cents: float = 0.0,
    bonus_messages: int = 0,
    plan_override: str | None = None,
    duration_days: int | None = None,
    max_redemptions: int | None = None,
    expires_at: datetime | None = None,
) -> dict:
    code = code.strip().upper()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coupons
                  (code, description, credit_cents, bonus_messages, plan_override,
                   duration_days, max_redemptions, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (code, description, credit_cents, bonus_messages, plan_override,
                 duration_days, max_redemptions, expires_at),
            )
            return dict(cur.fetchone())


def list_coupons() -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM coupons WHERE is_deleted = false ORDER BY created_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]


def update_coupon(code: str, **kwargs) -> dict:
    allowed = {
        "description", "credit_cents", "bonus_messages", "max_redemptions",
        "expires_at", "is_active", "plan_override", "duration_days",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        raise ValueError("No valid fields to update.")
    set_clause = ", ".join(f"{k} = %s" for k in updates) + ", updated_at = now()"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE coupons SET {set_clause} WHERE code = %s AND is_deleted = false RETURNING *",
                (*updates.values(), code.upper()),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Coupon not found.")
            return dict(row)


def delete_coupon(code: str) -> None:
    """Soft-delete a coupon. Existing redemptions and credits are unaffected."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE coupons
                SET is_deleted = true, is_active = false, deleted_at = now(), updated_at = now()
                WHERE code = %s AND is_deleted = false
                RETURNING code
                """,
                (code.upper(),),
            )
            if not cur.fetchone():
                raise ValueError("Coupon not found.")


def grant_coupon_to_user(
    uid: str,
    description: str,
    credit_cents: float = 0.0,
    bonus_messages: int = 0,
    duration_days: int | None = None,
    granted_by: str | None = None,
) -> dict:
    """
    Directly grant a credit/benefit to a specific user without them entering a code.
    Creates a single-use internal coupon (tag='grant') and immediately redeems it for the user.
    """
    # Verify the target user exists
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT uid FROM users WHERE uid = %s", (uid,))
            if not cur.fetchone():
                raise ValueError("User not found.")

    # Generate a unique internal code
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    code = f"GRANT-{suffix}"

    credit_expires_at = None
    if duration_days:
        credit_expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

    with get_db() as conn:
        with conn.cursor() as cur:
            # Create the single-use coupon
            cur.execute(
                """
                INSERT INTO coupons
                  (code, description, credit_cents, bonus_messages, duration_days,
                   max_redemptions, tag, is_active)
                VALUES (%s, %s, %s, %s, %s, 1, 'grant', true)
                """,
                (code, description, credit_cents, bonus_messages, duration_days),
            )
            # Record the redemption directly — no user action needed
            cur.execute(
                """
                INSERT INTO coupon_redemptions
                  (uid, coupon_code, credit_applied_cents, bonus_messages_applied, credit_expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (uid, code, credit_cents, bonus_messages, credit_expires_at),
            )
            # Mark it as already fully redeemed
            cur.execute(
                "UPDATE coupons SET redemption_count = 1 WHERE code = %s",
                (code,),
            )

    return {
        "code": code,
        "uid": uid,
        "description": description,
        "credit_cents": credit_cents,
        "bonus_messages": bonus_messages,
        "credit_expires_at": credit_expires_at.isoformat() if credit_expires_at else None,
    }


def get_coupon_redemptions(code: str) -> list[dict]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cr.*, u.display_name, u.email
                FROM coupon_redemptions cr
                JOIN users u ON cr.uid = u.uid
                WHERE cr.coupon_code = %s
                ORDER BY cr.redeemed_at DESC
                """,
                (code.upper(),),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("redeemed_at"):
                    d["redeemed_at"] = d["redeemed_at"].isoformat()
                if d.get("credit_expires_at"):
                    d["credit_expires_at"] = d["credit_expires_at"].isoformat()
                rows.append(d)
            return rows
