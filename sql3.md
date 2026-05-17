# Phase 3 SQL Migrations — Run in Supabase SQL Editor

```sql
-- Domain mastery tracking
CREATE TABLE IF NOT EXISTS domain_mastery (
  uid text references users(uid) on delete cascade,
  domain text not null,
  mastery_level float default 0,
  concept_count int default 0,
  reasoning_quality float default 0,
  learning_velocity float default 0,
  updated_at timestamptz default now(),
  primary key (uid, domain)
);

-- Generated Mind Signatures
CREATE TABLE IF NOT EXISTS mind_signatures (
  id uuid primary key default gen_random_uuid(),
  uid text references users(uid) on delete cascade,
  verification_hash text unique not null,
  capability_narrative text not null,
  domains jsonb not null,
  constellation_data jsonb not null,
  share_card_url text,
  generated_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS mind_signatures_uid_idx ON mind_signatures(uid);
CREATE INDEX IF NOT EXISTS mind_signatures_hash_idx ON mind_signatures(verification_hash);
```
