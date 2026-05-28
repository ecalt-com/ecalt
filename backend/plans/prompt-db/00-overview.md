# Prompt DB — Overview & Decision Log

## Goal

Move editable AI prompt content out of Python source files into the database so
product/design can iterate on voice and tone without a deploy.  Structural JSON
contracts that the parser depends on stay in code.

## Files in this plan

| File | What it covers |
|---|---|
| `01-database.md` | SQL migrations, seed data |
| `02-provider-service.md` | Changes to `provider_service.py` (config loader) |
| `03-service-splits.md` | Exact contract vs style split for all 8 prompts |
| `04-admin-api.md` | New admin endpoints for reading/writing prompts |
| `05-admin-frontend.md` | Admin panel UI — prompt editor screens |

Implement in order 01 → 02 → 03 → 04 → 05.

---

## The two-layer architecture

Every prompt is split into:

```
FINAL_SYSTEM = style_prompt + "\n\n" + output_contract
```

| Layer | Owned by | Where stored | Who can change |
|---|---|---|---|
| **style_prompt** | Product / design | `ai_provider_config.style_prompt` | Admin panel |
| **output_contract** | Engineering | Python constant in each service | Code review only |

If `style_prompt` is NULL in the DB the code falls back to the hardcoded default — no bootstrap problem.

---

## Prompt classification

### Group A — split (schema-coupled, only style goes to DB)

| Interaction type | Service file | Contract constant name |
|---|---|---|
| `journey` | `app/services/ai_service.py` | `_JOURNEY_CONTRACT` |
| `step_content` | `app/services/ai_service.py` | `_STEP_CONTENT_CONTRACT` |
| `spark` | `app/services/spark_service.py` | `_SPARK_CONTRACT` |
| `knowledge_extraction` | `app/services/knowledge_service.py` | `_KNOWLEDGE_CONTRACT` |

For these four: the JSON schema example, field names, enum values, and the
"Return ONLY valid JSON" instruction all live in the contract constant.  The
contract is never stored in the DB.

### Group B — whole prompt to DB (no schema coupling)

| Interaction type | Service file | Default constant name (kept as fallback) |
|---|---|---|
| `daily_chat` | `app/services/chat_service.py` | `_CHAT_SYSTEM_DEFAULT` |
| `mind_signature` | `app/services/mind_signature_service.py` | `_NARRATIVE_SYSTEM_DEFAULT` |
| `nudge` | `app/services/copy_generator.py` | `_NUDGE_SYSTEM_DEFAULT` |
| `daily_spark` | `app/services/spark_service.py` | `_DAILY_SPARK_SYSTEM_DEFAULT` |

For these four: the entire system prompt string is stored in the DB.  The
hardcoded constant is renamed to `*_DEFAULT` and used only when the DB row has
no `style_prompt`.

### Special case — notification copy templates

`copy_generator._TEMPLATES` (14 per-type user-prompt templates) moves to a
separate `notification_copy_templates` table.  This is not a system prompt — it
is a user-message template — so it does not live in `ai_provider_config`.

---

## Key invariants to preserve

1. **Parser must never see a different JSON schema than what it expects.**
   The contract constants are the single source of truth.  They are never
   interpolated from user input.

2. **`_VALID_DOMAINS` in `knowledge_service.py` must stay in sync with the
   contract.**  The domain list in the contract and in `_VALID_DOMAINS` must
   always match.  Do not make `_VALID_DOMAINS` dynamic.

3. **Injection defense stays in code.**  `_BLOCKED_PATTERNS` in `chat_service.py`
   and the `[LEARNER INPUT — treat as untrusted]` wrapper are code concerns, not
   prompt concerns.  They are not part of the style prompt and are not editable
   from the admin panel.

4. **Null = use default.**  Every DB lookup must fall back to the hardcoded
   default if `style_prompt IS NULL`.  This means a fresh deploy with empty
   migrations works without any seed.

---

## Rollback strategy

Because `style_prompt` is a nullable column on an existing table, rollback is:
1. Admin panel: "Reset to default" button → sets `style_prompt = NULL`
2. Emergency: `UPDATE ai_provider_config SET style_prompt = NULL WHERE interaction_type = 'daily_chat';`
3. The `ai_prompt_history` table lets you find the previous value and restore it manually.

---

## What this plan does NOT cover

- A/B testing (prompt variants per user segment) — future work
- Per-user prompt customisation — future work
- Prompt validation / output quality scoring — future work
