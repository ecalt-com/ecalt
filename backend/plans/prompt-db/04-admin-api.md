# Prompt DB — Phase 4: Admin API Endpoints

## File to modify

`app/api/v1/endpoints/admin.py`

All new endpoints are admin-only (existing `get_required_admin()` dependency).

---

## New Pydantic schemas (add to admin.py or a shared schemas file)

```python
class PromptRead(BaseModel):
    interaction_type:          str
    style_prompt:              str | None          # None = using hardcoded default
    style_prompt_is_default:   bool
    default_style_prompt:      str                 # always the hardcoded fallback text
    output_contract_hint:      str                 # short label, not the full contract
    style_prompt_updated_at:   str | None
    style_prompt_updated_by:   str | None
    provider:                  str
    model:                     str


class PromptUpdate(BaseModel):
    style_prompt: str = Field(..., min_length=10, max_length=8000)


class PromptHistoryEntry(BaseModel):
    id:                 int
    interaction_type:   str
    old_style_prompt:   str | None
    new_style_prompt:   str
    changed_by:         str
    changed_at:         str
    reset_to_default:   bool


class NotificationTemplateRead(BaseModel):
    notification_type:  str
    template:           str
    updated_at:         str | None
    updated_by:         str | None


class NotificationTemplateUpdate(BaseModel):
    template: str = Field(..., min_length=10, max_length=4000)
```

---

## Endpoint 1 — List all prompts

```
GET /admin/prompts
```

Returns all interaction types with their current style prompt status.

```python
@router.get("/prompts", response_model=list[PromptRead])
async def list_prompts(uid: str = Depends(get_required_admin)):
    configs = get_all_configs()   # updated in Phase 2
    # Map each config to PromptRead, adding a contract hint label
    CONTRACT_HINTS = {
        "journey":              "JSON: title, description, age_group, difficulty, steps[]",
        "step_content":         "JSON: content (structured markdown)",
        "spark":                "JSON: answer, mission{title, steps[]}",
        "knowledge_extraction": "JSON array: [{concept, domain}]",
        "daily_chat":           "Free-form conversational response",
        "mind_signature":       "3 plain-text paragraphs",
        "nudge":                "JSON: subject, body_html, short_message",
        "daily_spark":          "Free-form single question string",
        "onboarding":           "Not yet implemented",
        "fingerprint":          "Not yet implemented",
    }
    return [
        PromptRead(
            interaction_type=c["interaction_type"],
            style_prompt=c["style_prompt"],
            style_prompt_is_default=c["style_prompt_is_default"],
            default_style_prompt=c["default_style_prompt"],
            output_contract_hint=CONTRACT_HINTS.get(c["interaction_type"], ""),
            style_prompt_updated_at=c["style_prompt_updated_at"].isoformat() if c["style_prompt_updated_at"] else None,
            style_prompt_updated_by=c["style_prompt_updated_by"],
            provider=c["provider"],
            model=c["model"],
        )
        for c in configs
    ]
```

---

## Endpoint 2 — Get single prompt

```
GET /admin/prompts/{interaction_type}
```

```python
@router.get("/prompts/{interaction_type}", response_model=PromptRead)
async def get_prompt(
    interaction_type: str,
    uid: str = Depends(get_required_admin),
):
    configs = get_all_configs()
    cfg = next((c for c in configs if c["interaction_type"] == interaction_type), None)
    if not cfg:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    return PromptRead(...)  # same mapping as list_prompts
```

---

## Endpoint 3 — Update style prompt

```
PUT /admin/prompts/{interaction_type}
```

```python
@router.put("/prompts/{interaction_type}", status_code=204)
async def update_prompt(
    interaction_type: str,
    body: PromptUpdate,
    uid: str = Depends(get_required_admin),
):
    valid_types = set(DEFAULT_CONFIG.keys())
    if interaction_type not in valid_types:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    set_style_prompt(
        interaction_type=interaction_type,
        style_prompt=body.style_prompt,
        changed_by=uid,
        reset_to_default=False,
    )
```

Returns 204 No Content on success.

---

## Endpoint 4 — Reset to hardcoded default

```
POST /admin/prompts/{interaction_type}/reset
```

Sets `style_prompt = NULL` in the DB so the hardcoded default takes over.

```python
@router.post("/prompts/{interaction_type}/reset", status_code=204)
async def reset_prompt(
    interaction_type: str,
    uid: str = Depends(get_required_admin),
):
    valid_types = set(DEFAULT_CONFIG.keys())
    if interaction_type not in valid_types:
        raise HTTPException(status_code=404, detail="Unknown interaction type")
    set_style_prompt(
        interaction_type=interaction_type,
        style_prompt="",        # stored in history for audit
        changed_by=uid,
        reset_to_default=True,  # writes NULL to the DB column
    )
```

---

## Endpoint 5 — Prompt history

```
GET /admin/prompts/{interaction_type}/history?limit=20
```

```python
@router.get("/prompts/{interaction_type}/history", response_model=list[PromptHistoryEntry])
async def prompt_history(
    interaction_type: str,
    limit: int = Query(20, ge=1, le=100),
    uid: str = Depends(get_required_admin),
):
    rows = get_prompt_history(interaction_type, limit=limit)
    return [
        PromptHistoryEntry(
            id=r["id"],
            interaction_type=r["interaction_type"],
            old_style_prompt=r["old_style_prompt"],
            new_style_prompt=r["new_style_prompt"],
            changed_by=r["changed_by"],
            changed_at=r["changed_at"].isoformat(),
            reset_to_default=r["reset_to_default"],
        )
        for r in rows
    ]
```

---

## Endpoint 6 — List notification templates

```
GET /admin/notification-templates
```

```python
@router.get("/notification-templates", response_model=list[NotificationTemplateRead])
async def list_notification_templates(uid: str = Depends(get_required_admin)):
    rows = get_all_notification_templates()
    return [
        NotificationTemplateRead(
            notification_type=r["notification_type"],
            template=r["template"],
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
            updated_by=r["updated_by"],
        )
        for r in rows
    ]
```

---

## Endpoint 7 — Update notification template

```
PUT /admin/notification-templates/{notification_type}
```

```python
_VALID_NOTIFICATION_TYPES = {
    "daily_spark", "re_engagement", "cliffhanger_return", "connection_alert",
    "milestone_approach", "mind_signature_ready", "mind_signature_nudge",
    "world_event_hook", "streak_at_risk", "streak_lost", "streak_milestone",
    "journey_almost_done", "weekly_digest", "family_highlight",
}

@router.put("/notification-templates/{notification_type}", status_code=204)
async def update_notification_template(
    notification_type: str,
    body: NotificationTemplateUpdate,
    uid: str = Depends(get_required_admin),
):
    if notification_type not in _VALID_NOTIFICATION_TYPES:
        raise HTTPException(status_code=404, detail="Unknown notification type")
    set_notification_template(
        notification_type=notification_type,
        template=body.template,
        updated_by=uid,
    )
```

---

## Router registration

In `app/api/v1/router.py`, the admin router is already registered.
No new registration needed — all endpoints attach to the existing `/admin` prefix.

---

## Template variable documentation

Add a helper endpoint so the frontend can show available `{variables}` per template type
without hardcoding them in the UI:

```
GET /admin/notification-templates/variables
```

```python
TEMPLATE_VARIABLES: dict[str, list[str]] = {
    "daily_spark":          ["name", "topics", "angle"],
    "re_engagement":        ["name", "days_inactive", "domain"],
    "cliffhanger_return":   ["name", "topic"],
    "connection_alert":     ["name", "topic_a", "topic_b", "connection"],
    "milestone_approach":   ["name", "steps_remaining", "journey_title"],
    "mind_signature_ready": ["name", "domain"],
    "mind_signature_nudge": ["name", "mastery_pct", "domain"],
    "world_event_hook":     ["name", "event", "topic"],
    "streak_at_risk":       ["name", "streak_days"],
    "streak_lost":          ["name", "streak_days"],
    "streak_milestone":     ["name", "streak_days"],
    "journey_almost_done":  ["name", "steps_remaining", "journey_title"],
    "weekly_digest":        ["name", "new_concepts", "active_domains", "domains", "journeys_touched"],
    "family_highlight":     ["name", "summary"],
}

@router.get("/notification-templates/variables")
async def template_variables(uid: str = Depends(get_required_admin)):
    return TEMPLATE_VARIABLES
```

---

## Checklist

- [ ] `PromptRead`, `PromptUpdate`, `PromptHistoryEntry`, `NotificationTemplateRead`, `NotificationTemplateUpdate` schemas added
- [ ] `GET /admin/prompts` implemented
- [ ] `GET /admin/prompts/{type}` implemented
- [ ] `PUT /admin/prompts/{type}` implemented
- [ ] `POST /admin/prompts/{type}/reset` implemented
- [ ] `GET /admin/prompts/{type}/history` implemented
- [ ] `GET /admin/notification-templates` implemented
- [ ] `PUT /admin/notification-templates/{type}` implemented
- [ ] `GET /admin/notification-templates/variables` implemented
- [ ] All endpoints require admin auth
- [ ] `CONTRACT_HINTS` and `TEMPLATE_VARIABLES` dicts kept up to date if new interaction types are added
