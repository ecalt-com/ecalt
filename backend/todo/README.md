# Pending DB Migrations

SQL files here need to be run manually against the Supabase database before the related features work correctly.

---

## add_cache_tracking.sql

**Feature:** OpenAI prompt cache hit measurement  
**Status:** Code is deployed. DB migration pending.

**What it does:** Adds a `cached_input_tokens` column to `token_usage` so the app can record how many tokens were served from OpenAI's automatic prefix cache on each request.

**Run it:**
1. Open Supabase dashboard → SQL Editor
2. Paste and run the contents of `add_cache_tracking.sql`

**After running:** On any `daily_chat` conversation that reaches 4–5 turns, `cached_input_tokens` in `token_usage` will start accumulating. The admin `/admin/usage` endpoint will then return non-zero `cache.total_cached_input_tokens` and `cache.cache_hit_pct`.

**Verify:**
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'token_usage' AND column_name = 'cached_input_tokens';
```
