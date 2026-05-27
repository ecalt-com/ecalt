# Coupon System — Backend Extension Plan

> Scope: Extend the existing coupon API from a minimal CRUD stub to a production-grade promotion engine.  
> Stack: FastAPI + PostgreSQL (Supabase). All endpoints live under `/api/v1/coupons/`.

---

## Current State Audit

### What exists today

| Endpoint | Method | Status |
|---|---|---|
| `/apply` | POST | ✅ Works |
| `/admin` | GET | ✅ Returns all coupons, no pagination |
| `/admin` | POST | ✅ Creates a coupon |
| `/admin/{code}` | PATCH | ✅ Updates subset of fields |
| `/admin/{code}/redemptions` | GET | ✅ Returns raw redemption rows |

### Known gaps

| Gap | Impact |
|---|---|
| No `GET /admin/{code}` (single fetch) | UI can't load one coupon without fetching all |
| No `DELETE /admin/{code}` | Can only deactivate; no cleanup path |
| `update_coupon()` blocks `plan_override` and `duration_days` | Those fields can never be edited post-creation |
| No pagination or filtering on list | Will degrade at 50+ coupons |
| No analytics endpoint | Zero insight into campaign performance |
| `plan_override` stored but never enforced in `check_budget()` | Dead field in schema |
| No bulk-generate endpoint | Referral programs require unique per-user codes |
| No per-user redemption revocation | No fraud remediation path |
| No `updated_at` column on `coupons` table | Audit trail is blind to edits |
| No tags/categories | Can't segment campaigns (launch vs referral vs conference) |

---

## Phase 1 — CRUD Completeness

### 1.1 New endpoint: `GET /admin/{code}`

Return a single coupon with its redemption count. Needed by the inline-edit UI.

```python
@router.get("/admin/{code}")
def admin_get(code: str, uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import get_coupon
    try:
        return get_coupon(code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

**Service function** (`get_coupon`):
```python
def get_coupon(code: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM coupons WHERE code = %s", (code.upper(),))
            row = cur.fetchone()
    if not row:
        raise ValueError("Coupon not found.")
    return dict(row)
```

---

### 1.2 New endpoint: `DELETE /admin/{code}`

Soft delete — sets `is_deleted = true` and `is_active = false`. Does NOT purge redemption history (needed for credit tracking). Hard purge is out of scope.

**DB migration:**
```sql
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS is_deleted boolean NOT NULL DEFAULT false;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Keep existing redemptions intact — only future apply attempts should fail
-- The apply_coupon service already checks is_active, so setting is_active=false is sufficient.
-- is_deleted is the additional UI signal that the coupon is gone intentionally.
```

```python
@router.delete("/admin/{code}", status_code=204)
def admin_delete(code: str, uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import delete_coupon
    try:
        delete_coupon(code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

**Service function:**
```python
def delete_coupon(code: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE coupons
                SET is_deleted = true, is_active = false, deleted_at = now()
                WHERE code = %s AND is_deleted = false
                RETURNING code
                """,
                (code.upper(),),
            )
            if not cur.fetchone():
                raise ValueError("Coupon not found.")
```

**Update `list_coupons` to exclude deleted by default:**
```python
def list_coupons(include_deleted: bool = False) -> list[dict]:
    where = "" if include_deleted else "WHERE is_deleted = false"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM coupons {where} ORDER BY created_at DESC")
            return [dict(r) for r in cur.fetchall()]
```

---

### 1.3 Fix `update_coupon` — allow `plan_override` and `duration_days`

Current `allowed` set in `coupon_service.py:105` excludes `plan_override` and `duration_days`. Add them:

```python
allowed = {
    "description", "credit_cents", "bonus_messages",
    "max_redemptions", "expires_at", "is_active",
    "plan_override", "duration_days",           # ← add these
}
```

Also always set `updated_at = now()` on any update:
```python
set_clause = ", ".join(f"{k} = %s" for k in updates) + ", updated_at = now()"
```

**Update `UpdateCouponRequest` in `coupons.py`:**
```python
class UpdateCouponRequest(BaseModel):
    description: Optional[str] = None
    credit_cents: Optional[float] = None
    bonus_messages: Optional[int] = None
    max_redemptions: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None
    plan_override: Optional[str] = None    # ← add
    duration_days: Optional[int] = None   # ← add
```

---

### 1.4 Pagination + filtering on `GET /admin`

```python
@router.get("/admin")
def admin_list(
    uid: str = Depends(get_admin_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),   # "active" | "inactive" | "expired" | "depleted"
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None),        # code prefix search
):
    return list_coupons_paginated(page=page, per_page=per_page, status=status, tag=tag, q=q)
```

**Service function:**
```python
def list_coupons_paginated(
    page: int = 1,
    per_page: int = 50,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> dict:
    conditions = ["is_deleted = false"]
    params: list = []

    if status == "active":
        conditions.append("is_active = true AND (expires_at IS NULL OR expires_at > now())")
    elif status == "inactive":
        conditions.append("is_active = false")
    elif status == "expired":
        conditions.append("expires_at IS NOT NULL AND expires_at <= now()")
    elif status == "depleted":
        conditions.append("max_redemptions IS NOT NULL AND redemption_count >= max_redemptions")

    if tag:
        conditions.append("tag = %s")
        params.append(tag)

    if q:
        conditions.append("code ILIKE %s")
        params.append(f"{q.upper()}%")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * per_page

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM coupons {where}", params)
            total = cur.fetchone()[0]
            cur.execute(
                f"SELECT * FROM coupons {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                [*params, per_page, offset],
            )
            items = [dict(r) for r in cur.fetchall()]

    return {"coupons": items, "total": total, "page": page, "per_page": per_page}
```

---

## Phase 2 — Analytics

### 2.1 Global coupon stats: `GET /admin/stats`

Returns aggregate metrics across all coupons. Powers the stats cards at the top of the admin Coupons tab.

```python
@router.get("/admin/stats")
def admin_stats(uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import get_coupon_stats
    return get_coupon_stats()
```

**Service function:**
```python
def get_coupon_stats() -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  COUNT(*) FILTER (WHERE is_active AND is_deleted = false)                AS active_coupons,
                  COUNT(*) FILTER (WHERE is_deleted = false)                              AS total_coupons,
                  SUM(redemption_count) FILTER (WHERE is_deleted = false)                 AS total_redemptions,
                  SUM(credit_cents * redemption_count) FILTER (WHERE is_deleted = false)  AS total_credit_issued_cents
                FROM coupons
            """)
            summary = dict(cur.fetchone())

            cur.execute("""
                SELECT
                  SUM(credit_applied_cents)   AS total_credit_applied_cents,
                  SUM(bonus_messages_applied) AS total_bonus_messages_applied,
                  COUNT(DISTINCT uid)         AS unique_redeemers
                FROM coupon_redemptions
            """)
            redemption_summary = dict(cur.fetchone())

    return {**summary, **redemption_summary}
```

**Response shape:**
```json
{
  "active_coupons": 4,
  "total_coupons": 12,
  "total_redemptions": 347,
  "total_credit_issued_cents": 17350.0,
  "total_credit_applied_cents": 17350.0,
  "total_bonus_messages_applied": 820,
  "unique_redeemers": 289
}
```

---

### 2.2 Per-coupon stats: `GET /admin/{code}/stats`

Breakdown for a single coupon — use rate over time, useful for campaign retrospectives.

```python
@router.get("/admin/{code}/stats")
def admin_coupon_stats(code: str, uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import get_single_coupon_stats
    return get_single_coupon_stats(code)
```

**Service function:**
```python
def get_single_coupon_stats(code: str) -> dict:
    code = code.upper()
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM coupons WHERE code = %s AND is_deleted = false", (code,))
            coupon = cur.fetchone()
            if not coupon:
                raise ValueError("Coupon not found.")

            cur.execute("""
                SELECT
                  DATE_TRUNC('day', redeemed_at) AS day,
                  COUNT(*)                        AS redemptions,
                  SUM(credit_applied_cents)       AS credit_cents
                FROM coupon_redemptions
                WHERE coupon_code = %s
                GROUP BY 1
                ORDER BY 1
            """, (code,))
            daily = [dict(r) for r in cur.fetchall()]

            fill_rate = None
            if coupon["max_redemptions"]:
                fill_rate = round(coupon["redemption_count"] / coupon["max_redemptions"] * 100, 1)

    return {
        "coupon": dict(coupon),
        "fill_rate_pct": fill_rate,
        "daily_redemptions": daily,
    }
```

---

## Phase 3 — Advanced Features

### 3.1 Coupon tags/categories

**DB migration:**
```sql
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS tag text;
-- Common tags: 'launch', 'referral', 'conference', 'influencer', 'beta', 'support'
```

Add `tag` to `CreateCouponRequest` and `UpdateCouponRequest`. Include in list filtering (already wired in Phase 1.4).

---

### 3.2 Bulk-generate unique codes: `POST /admin/bulk-generate`

Generates N unique single-use codes sharing the same reward configuration. Needed for referral programs and conference QR codes.

```python
class BulkGenerateRequest(BaseModel):
    prefix: str                           # e.g. "CONF26" → codes like "CONF26-A3X9"
    count: int = Field(ge=1, le=1000)
    description: str
    credit_cents: float = 0.0
    bonus_messages: int = 0
    duration_days: Optional[int] = None
    expires_at: Optional[datetime] = None
    tag: Optional[str] = None

@router.post("/admin/bulk-generate")
def admin_bulk_generate(body: BulkGenerateRequest, uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import bulk_generate_coupons
    codes = bulk_generate_coupons(**body.model_dump())
    return {"created": len(codes), "codes": codes}
```

**Service function:**
```python
import secrets, string

def bulk_generate_coupons(
    prefix: str,
    count: int,
    description: str,
    credit_cents: float = 0.0,
    bonus_messages: int = 0,
    duration_days: int | None = None,
    expires_at = None,
    tag: str | None = None,
) -> list[str]:
    prefix = prefix.strip().upper()
    alphabet = string.ascii_uppercase + string.digits
    codes = []
    seen = set()

    while len(codes) < count:
        suffix = ''.join(secrets.choice(alphabet) for _ in range(6))
        code = f"{prefix}-{suffix}"
        if code not in seen:
            seen.add(code)
            codes.append(code)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO coupons
                  (code, description, credit_cents, bonus_messages, duration_days,
                   max_redemptions, expires_at, tag)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
                ON CONFLICT (code) DO NOTHING
                """,
                [(c, description, credit_cents, bonus_messages, duration_days, expires_at, tag)
                 for c in codes],
            )
    return codes
```

Note: `max_redemptions = 1` is hardcoded for bulk-generated codes — each code is single-use by design.

---

### 3.3 Implement `plan_override` in `check_budget()`

The `plan_override` field exists in the schema but `check_budget()` in `subscription_service.py` ignores it. When set, it should treat the user as if they are on that plan for the duration of their active redemption.

**In `subscription_service.py`** — extend `get_coupon_extras()` to also return a plan override if active:

```python
def get_coupon_extras(uid: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                  COALESCE(SUM(cr.credit_applied_cents), 0)    AS extra_credits,
                  COALESCE(SUM(cr.bonus_messages_applied), 0)  AS bonus_messages,
                  -- Return the most generous plan override that hasn't expired
                  (
                    SELECT c.plan_override
                    FROM coupon_redemptions cr2
                    JOIN coupons c ON c.code = cr2.coupon_code
                    WHERE cr2.uid = %s
                      AND c.plan_override IS NOT NULL
                      AND (cr2.credit_expires_at IS NULL OR cr2.credit_expires_at > now())
                    ORDER BY c.created_at DESC
                    LIMIT 1
                  ) AS plan_override
                FROM coupon_redemptions cr
                WHERE cr.uid = %s
                  AND (cr.credit_expires_at IS NULL OR cr.credit_expires_at > now())
            """, (uid, uid))
            row = dict(cur.fetchone())

    return {
        "extra_credits_cents": float(row["extra_credits"] or 0),
        "bonus_messages": int(row["bonus_messages"] or 0),
        "plan_override": row.get("plan_override"),
    }
```

**In `check_budget()`** — when `plan_override` is present, load the override plan's budget instead:
```python
extras = get_coupon_extras(uid)
effective_plan = get_user_plan(uid)

if extras.get("plan_override"):
    override = get_plan_config(extras["plan_override"])  # load from plan_configs
    if override:
        effective_plan = override
```

---

### 3.4 Revoke a user's redemption: `DELETE /admin/{code}/redemptions/{uid}`

Fraud/abuse remediation path. Removes the redemption record so the credit is no longer counted.

```python
@router.delete("/admin/{code}/redemptions/{uid}", status_code=204)
def admin_revoke_redemption(code: str, uid: str, admin_uid: str = Depends(get_admin_user)):
    from app.services.coupon_service import revoke_redemption
    try:
        revoke_redemption(code, uid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

**Service function:**
```python
def revoke_redemption(code: str, uid: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM coupon_redemptions WHERE coupon_code = %s AND uid = %s RETURNING id",
                (code.upper(), uid),
            )
            if not cur.fetchone():
                raise ValueError("Redemption not found.")
            cur.execute(
                "UPDATE coupons SET redemption_count = GREATEST(0, redemption_count - 1) WHERE code = %s",
                (code.upper(),),
            )
```

---

## Phase 4 — Input Validation & Data Quality

### 4.1 Code format validation

Add a validator to `CreateCouponRequest`:

```python
from pydantic import field_validator
import re

class CreateCouponRequest(BaseModel):
    code: str
    ...

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(r'^[A-Z0-9][A-Z0-9_-]{1,29}$', v):
            raise ValueError("Code must be 2–30 characters, uppercase letters, digits, hyphens, or underscores only.")
        return v
```

### 4.2 Prevent creating zero-value coupons accidentally

```python
    @model_validator(mode="after")
    def at_least_one_benefit(self) -> "CreateCouponRequest":
        if self.credit_cents == 0 and self.bonus_messages == 0 and self.plan_override is None:
            raise ValueError("Coupon must grant at least one benefit: credit_cents, bonus_messages, or plan_override.")
        return self
```

### 4.3 Add `updated_at` trigger in Postgres

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER coupons_set_updated_at
BEFORE UPDATE ON coupons
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## Complete DB Migration Summary

```sql
-- Run in order

ALTER TABLE coupons ADD COLUMN IF NOT EXISTS is_deleted  boolean      NOT NULL DEFAULT false;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS deleted_at  timestamptz;
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS updated_at  timestamptz  DEFAULT now();
ALTER TABLE coupons ADD COLUMN IF NOT EXISTS tag         text;

CREATE INDEX IF NOT EXISTS coupons_is_deleted_idx   ON coupons (is_deleted);
CREATE INDEX IF NOT EXISTS coupons_tag_idx           ON coupons (tag);
CREATE INDEX IF NOT EXISTS coupons_is_active_idx     ON coupons (is_active);
CREATE INDEX IF NOT EXISTS coupons_expires_at_idx    ON coupons (expires_at);
CREATE INDEX IF NOT EXISTS coupon_redemptions_uid_idx ON coupon_redemptions (uid);
```

---

## Final Endpoint Summary

| Method | Path | Phase | Description |
|---|---|---|---|
| POST | `/apply` | existing | User applies a coupon |
| GET | `/admin` | extended | List with pagination + filters |
| POST | `/admin` | existing | Create a coupon |
| GET | `/admin/stats` | new | Global coupon aggregate stats |
| GET | `/admin/{code}` | new | Fetch a single coupon |
| PATCH | `/admin/{code}` | extended | Update (now includes plan_override, duration_days) |
| DELETE | `/admin/{code}` | new | Soft-delete a coupon |
| GET | `/admin/{code}/stats` | new | Per-coupon analytics + daily chart data |
| GET | `/admin/{code}/redemptions` | existing | List who redeemed |
| DELETE | `/admin/{code}/redemptions/{uid}` | new | Revoke one user's redemption |
| POST | `/admin/bulk-generate` | new | Generate N unique single-use codes |

---

## Implementation Order

1. **Do first (unblocks UI):** Phase 1 — `GET /admin/{code}`, `DELETE /admin/{code}`, fix `update_coupon` allowed fields, add `is_deleted` + `updated_at` columns
2. **Do second (analytics):** Phase 2 — `GET /admin/stats`, `GET /admin/{code}/stats`
3. **Do third (growth):** Phase 3.1 tags + Phase 3.2 bulk-generate
4. **Do last (complex):** Phase 3.3 `plan_override` enforcement, Phase 3.4 revoke redemption
5. **Ongoing:** Phase 4 validators (can add to Phase 1 PRs)
