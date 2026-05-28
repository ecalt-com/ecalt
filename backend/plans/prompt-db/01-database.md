# Prompt DB — Phase 1: Database

## Files to create/modify

- New migration file: `migrations/NNNN_prompt_db.sql` (add after existing migrations)

---

## Migration SQL

Run these three blocks in order in a single migration.

### Block 1 — Extend `ai_provider_config`

```sql
-- Add nullable style_prompt column.
-- NULL means "use hardcoded default" — safe for zero-downtime deploy.
ALTER TABLE ai_provider_config
    ADD COLUMN IF NOT EXISTS style_prompt        TEXT,
    ADD COLUMN IF NOT EXISTS style_prompt_updated_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS style_prompt_updated_by  TEXT;
```

No backfill needed.  Existing rows get NULL, code falls back to defaults.

### Block 2 — Audit history table

```sql
CREATE TABLE IF NOT EXISTS ai_prompt_history (
    id                  BIGSERIAL PRIMARY KEY,
    interaction_type    TEXT        NOT NULL,
    old_style_prompt    TEXT,                       -- NULL on first-ever edit
    new_style_prompt    TEXT        NOT NULL,
    changed_by          TEXT        NOT NULL,        -- Firebase uid of admin
    changed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    reset_to_default    BOOLEAN     NOT NULL DEFAULT FALSE
);

CREATE INDEX ai_prompt_history_type_idx ON ai_prompt_history (interaction_type, changed_at DESC);
```

### Block 3 — Notification copy templates

```sql
CREATE TABLE IF NOT EXISTS notification_copy_templates (
    notification_type   TEXT        PRIMARY KEY,
    template            TEXT        NOT NULL,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by          TEXT
);
```

Seed with the 14 default templates from `copy_generator._TEMPLATES` (see section below).

---

## Seed data

### Seed notification_copy_templates

Run this after Block 3.  Values are the current hardcoded templates from
`app/services/copy_generator.py` — copy them verbatim.

```sql
INSERT INTO notification_copy_templates (notification_type, template) VALUES

('daily_spark',
 'User''s name: {name}. Recent topics: {topics}. Today''s angle: {angle}. '
 'Send a personalised daily curiosity nudge that connects to what they''ve been exploring. '
 'Make the short_message feel like a fascinating question from a smart friend.'),

('re_engagement',
 'User''s name: {name}. Inactive for {days_inactive} days. Favourite domain: {domain}. '
 'Write a warm, non-pushy message that sparks curiosity about {domain} — '
 'give them one specific surprising fact or question about it right in the message body. '
 'Don''t say ''we miss you'', just make them curious.'),

('cliffhanger_return',
 'User''s name: {name}. They left a learning conversation about ''{topic}'' without resolving it. '
 'Reference the specific topic and tease the unresolved angle — '
 'make them feel like they''d genuinely regret not finding the answer. '
 'The short_message should feel like a friend texting: ''hey wait, did you ever figure out why...?'''),

('connection_alert',
 'User''s name: {name}. Their topics ''{topic_a}'' and ''{topic_b}'' share a surprising connection: {connection}. '
 'Deliver this cross-domain insight in a way that makes them go ''wait, really?'' '
 'Lead with the surprising fact.'),

('milestone_approach',
 'User''s name: {name}. Only {steps_remaining} step(s) away from completing their ''{journey_title}'' journey. '
 'Motivate them to finish — make the finish line feel close and achievable. '
 'Be specific about the journey.'),

('mind_signature_ready',
 'User''s name: {name}. They''ve earned a new Mind Signature in {domain}. '
 'Celebrate the achievement genuinely — explain what a Mind Signature means '
 'and invite them to see their personalised knowledge constellation.'),

('mind_signature_nudge',
 'User''s name: {name}. They are {mastery_pct}% of the way to earning a Mind Signature in {domain}. '
 'Tease what a Mind Signature is (a personalised constellation of their intellectual range) '
 'and show them how close they are. Make it feel worth pushing for.'),

('world_event_hook',
 'User''s name: {name}. A real-world event ({event}) connects to their learning topic ''{topic}''. '
 'Show them exactly why this matters to what they''ve been studying — be specific.'),

('streak_at_risk',
 'User''s name: {name}. They have a {streak_days}-day learning streak that will break tonight '
 'if they don''t do one session. Write an urgent but warm nudge — '
 'not scary, just a friendly ''hey, don''t let this slip''. '
 'Make it feel low-effort: ''5 minutes is enough''.'),

('streak_lost',
 'User''s name: {name}. They just lost their {streak_days}-day learning streak. '
 'Write a compassionate, forward-looking message. Acknowledge the loss briefly but focus on '
 'starting fresh — make day 1 feel exciting, not like punishment. '
 'No guilt-tripping.'),

('streak_milestone',
 'User''s name: {name}. They just hit a {streak_days}-day learning streak milestone. '
 'Celebrate it warmly and specifically — make them feel like this is a real achievement '
 'worth being proud of. Be enthusiastic but not over-the-top.'),

('journey_almost_done',
 'User''s name: {name}. They are {steps_remaining} step(s) away from finishing '
 'their ''{journey_title}'' journey. '
 'Motivate them across the finish line — most people who get this close never finish. '
 'Make completing it feel meaningful and easy.'),

('weekly_digest',
 'User''s name: {name}. This week they explored {new_concepts} new concepts across '
 '{active_domains} domains ({domains}), and touched {journeys_touched} learning journey(s). '
 'Write a warm, celebratory weekly summary that makes them feel like they''ve genuinely '
 'built something. Reference the specific domains they explored.'),

('family_highlight',
 'User''s name: {name}. Weekly family learning summary: {summary}. '
 'Write a warm summary that celebrates the family''s curiosity this week.')

ON CONFLICT (notification_type) DO NOTHING;
```

---

## Indexes / constraints summary

| Table | New columns | Index |
|---|---|---|
| `ai_provider_config` | `style_prompt TEXT`, `style_prompt_updated_at TIMESTAMPTZ`, `style_prompt_updated_by TEXT` | none (PK already on `interaction_type`) |
| `ai_prompt_history` | full new table | `(interaction_type, changed_at DESC)` |
| `notification_copy_templates` | full new table | PK on `notification_type` |

---

## Verify migration

After running, confirm with:

```sql
-- Should show new columns
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'ai_provider_config'
ORDER BY ordinal_position;

-- Should show 14 rows
SELECT notification_type FROM notification_copy_templates ORDER BY notification_type;

-- History table exists
SELECT COUNT(*) FROM ai_prompt_history;
```
