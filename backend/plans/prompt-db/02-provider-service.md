# Prompt DB — Phase 2: Provider Service Changes

## File to modify

`app/services/provider_service.py`

This file is the central hub that all services call.  It already owns
`get_config(interaction_type)` which returns provider + model from the DB.
We extend it to also return `style_prompt` and add the write/history helpers.

---

## Step 1 — Add `DEFAULT_STYLE_PROMPTS` dict

Add this constant near the top of the file, after `DEFAULT_CONFIG`.
These are the verbatim current hardcoded prompts from each service file,
trimmed to the style layer only (see `03-service-splits.md` for exact text).

```python
# Fallback style prompts used when DB row has style_prompt = NULL.
# Keys must match interaction_type values in DEFAULT_CONFIG.
DEFAULT_STYLE_PROMPTS: dict[str, str] = {
    "daily_chat":           _CHAT_STYLE_DEFAULT,           # imported or defined below
    "nudge":                _NUDGE_STYLE_DEFAULT,
    "onboarding":           "",                            # not yet implemented
    "fingerprint":          "",
    "mind_signature":       _NARRATIVE_STYLE_DEFAULT,
    "spark":                _SPARK_STYLE_DEFAULT,
    "daily_spark":          _DAILY_SPARK_STYLE_DEFAULT,
    "knowledge_extraction": _KNOWLEDGE_STYLE_DEFAULT,
    "journey":              _JOURNEY_STYLE_DEFAULT,
    "step_content":         _STEP_CONTENT_STYLE_DEFAULT,
}
```

The actual string values for each key live in `03-service-splits.md`.
When implementing, define them as module-level string constants in this file
(so they are accessible as fallbacks without importing from the service files,
which would create circular imports).

---

## Step 2 — Update `get_config()` return shape

Current signature:
```python
def get_config(interaction_type: str) -> dict:
    # returns {"provider": str, "model": str}
```

New signature (backwards-compatible — add `style_prompt` key):
```python
def get_config(interaction_type: str) -> dict:
    # returns {"provider": str, "model": str, "style_prompt": str}
```

Implementation changes:

```python
def get_config(interaction_type: str) -> dict:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT provider, model, style_prompt
                    FROM ai_provider_config
                    WHERE interaction_type = %s
                    """,
                    (interaction_type,),
                )
                row = cur.fetchone()
                if row:
                    fallback = DEFAULT_STYLE_PROMPTS.get(interaction_type, "")
                    return {
                        "provider":     row["provider"],
                        "model":        row["model"],
                        "style_prompt": row["style_prompt"] or fallback,
                    }
    except Exception:
        pass

    default = DEFAULT_CONFIG.get(interaction_type, DEFAULT_CONFIG["daily_chat"])
    return {
        "provider":     default["provider"],
        "model":        default["model"],
        "style_prompt": DEFAULT_STYLE_PROMPTS.get(interaction_type, ""),
    }
```

Key rules:
- `row["style_prompt"] or fallback` — empty string in DB also falls back.
- Never raise from this function; return defaults on any DB error.

---

## Step 3 — Add `set_style_prompt()`

New function — persists a style prompt and writes an audit row.

```python
def set_style_prompt(
    interaction_type: str,
    style_prompt: str,
    changed_by: str,
    reset_to_default: bool = False,
) -> None:
    """
    Upsert style_prompt for an interaction type and record audit history.
    Pass reset_to_default=True (and style_prompt="") to restore code default.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            # Read current value for history
            cur.execute(
                "SELECT style_prompt FROM ai_provider_config WHERE interaction_type = %s",
                (interaction_type,),
            )
            row = cur.fetchone()
            old_prompt = row["style_prompt"] if row else None

            # Upsert main config row
            new_value = None if reset_to_default else style_prompt
            cur.execute(
                """
                INSERT INTO ai_provider_config
                    (interaction_type, provider, model, style_prompt,
                     style_prompt_updated_at, style_prompt_updated_by)
                VALUES (
                    %s,
                    COALESCE((SELECT provider FROM ai_provider_config WHERE interaction_type = %s),
                             %s),
                    COALESCE((SELECT model FROM ai_provider_config WHERE interaction_type = %s),
                             %s),
                    %s, now(), %s
                )
                ON CONFLICT (interaction_type) DO UPDATE SET
                    style_prompt             = EXCLUDED.style_prompt,
                    style_prompt_updated_at  = now(),
                    style_prompt_updated_by  = EXCLUDED.style_prompt_updated_by
                """,
                (
                    interaction_type,
                    interaction_type, DEFAULT_CONFIG.get(interaction_type, DEFAULT_CONFIG["daily_chat"])["provider"],
                    interaction_type, DEFAULT_CONFIG.get(interaction_type, DEFAULT_CONFIG["daily_chat"])["model"],
                    new_value, changed_by,
                ),
            )

            # Write history row
            cur.execute(
                """
                INSERT INTO ai_prompt_history
                    (interaction_type, old_style_prompt, new_style_prompt,
                     changed_by, reset_to_default)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    interaction_type,
                    old_prompt,
                    style_prompt,   # store what was sent even on reset (for audit)
                    changed_by,
                    reset_to_default,
                ),
            )
```

Note: the INSERT uses COALESCE subselects to avoid overwriting provider/model
when upserting a prompt-only change.  A cleaner alternative is to require the
row to exist first (always INSERT during migrations), but the COALESCE approach
is safer for the admin flow where model config may not yet be in the DB.

---

## Step 4 — Add `get_prompt_history()`

Used by the admin panel to show the audit log.

```python
def get_prompt_history(interaction_type: str, limit: int = 20) -> list[dict]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, interaction_type, old_style_prompt, new_style_prompt,
                           changed_by, changed_at, reset_to_default
                    FROM ai_prompt_history
                    WHERE interaction_type = %s
                    ORDER BY changed_at DESC
                    LIMIT %s
                    """,
                    (interaction_type, limit),
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
```

---

## Step 5 — Add `get_notification_template()` and `set_notification_template()`

```python
def get_notification_template(notification_type: str) -> str | None:
    """Return the DB template for a notification type, or None if not found."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT template FROM notification_copy_templates WHERE notification_type = %s",
                    (notification_type,),
                )
                row = cur.fetchone()
                return row["template"] if row else None
    except Exception:
        return None


def set_notification_template(
    notification_type: str,
    template: str,
    updated_by: str,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification_copy_templates
                    (notification_type, template, updated_at, updated_by)
                VALUES (%s, %s, now(), %s)
                ON CONFLICT (notification_type) DO UPDATE SET
                    template   = EXCLUDED.template,
                    updated_at = now(),
                    updated_by = EXCLUDED.updated_by
                """,
                (notification_type, template, updated_by),
            )


def get_all_notification_templates() -> list[dict]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT notification_type, template, updated_at, updated_by "
                    "FROM notification_copy_templates ORDER BY notification_type"
                )
                return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []
```

---

## Step 6 — Update `get_all_configs()` to include style_prompt

This powers the admin "AI Config" list page:

```python
def get_all_configs() -> list[dict]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT interaction_type, provider, model, "
                    "       style_prompt, style_prompt_updated_at, style_prompt_updated_by "
                    "FROM ai_provider_config"
                )
                db_rows = {r["interaction_type"]: dict(r) for r in cur.fetchall()}
    except Exception:
        db_rows = {}

    result = []
    for itype, default in DEFAULT_CONFIG.items():
        row = db_rows.get(itype, {})
        result.append({
            "interaction_type":          itype,
            "provider":                  row.get("provider", default["provider"]),
            "model":                     row.get("model", default["model"]),
            "style_prompt":              row.get("style_prompt"),         # None = using default
            "style_prompt_is_default":   row.get("style_prompt") is None,
            "style_prompt_updated_at":   row.get("style_prompt_updated_at"),
            "style_prompt_updated_by":   row.get("style_prompt_updated_by"),
            "default_style_prompt":      DEFAULT_STYLE_PROMPTS.get(itype, ""),
        })
    return result
```

---

## Imports to add at top of provider_service.py

None new — all helpers use the existing `get_db()` and built-ins.

---

## Checklist

- [ ] `DEFAULT_STYLE_PROMPTS` dict added (strings from `03-service-splits.md`)
- [ ] `get_config()` returns `style_prompt` key
- [ ] `set_style_prompt()` added
- [ ] `get_prompt_history()` added
- [ ] `get_notification_template()` / `set_notification_template()` / `get_all_notification_templates()` added
- [ ] `get_all_configs()` updated
- [ ] No circular imports (provider_service must not import from service files)
