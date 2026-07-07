# Cost Impact — Model Upgrades & Plan Changes

Companion to [README.md](README.md). All numbers grounded in **live prod data pulled 2026-07-07** from `usage_by_interaction`, `step_content`, and `journeys`, priced with the same rates the app itself uses (`COST_PER_TOKEN`, `provider_service.py:467`).

## TL;DR

- **Today's total AI spend is ~3 cents/month.** Volume is tiny (3 journeys, 12 step generations, 1 spark in the last 30 days), so this decision is about *per-unit* economics, not current bills.
- Recommended config raises the cost of a full 8-step journey from **~0.4¢ → ~4.5¢ (~10×)** — still less than 1/1000th of a typical subscription price.
- Even at **1,000 journeys/month** (≈300× current volume) the recommended config costs **~$50/month**.
- One-time backfill of all 622 existing cached steps: **~$1.90**.

---

## 1. Current usage (prod, last 30 days)

| interaction_type | calls | avg in tok | avg out tok | 30-day cost |
|---|---|---|---|---|
| quiz | 34 | 1,620 | 619 | 2.09¢ |
| step_content | 12 | 907 | 604 | 0.60¢ |
| journey_tutor | 20 | 694 | 150 | 0.26¢ |
| journey | 3 | 644 | 582 | 0.09¢ |
| spark | 1 | 457 | 182 | 0.01¢ |
| others (daily_spark, chat, mind_signature) | 4 | — | — | 0.03¢ |
| **Total** | | | | **≈3.1¢ / month** |

Note the quality signal hiding in this table: `step_content` averages only **604 output tokens (~450 words)** against prompt targets of 420–900 words — the cheap model is under-delivering even on length.

## 2. Model prices used (per 1M tokens, from `COST_PER_TOKEN`)

| model | input | output |
|---|---|---|
| gpt-4.1-nano (current: journey, spark) | $0.10 | $0.40 |
| gpt-4o-mini (current: step_content, quiz) | $0.15 | $0.60 |
| gpt-4.1-mini (proposed: step_content, spark) | $0.40 | $1.60 |
| gpt-4.1 (proposed: journey; premium option: steps) | $2.00 | $8.00 |
| claude-sonnet-4-6 (premium option) | $3.00 | $15.00 |

## 3. Per-unit cost: one full journey (generate + warm 8 steps)

Token assumptions for the proposed config reflect Phases 2–3: bigger prompts (outline, prior-step anchors, learner profile, seed facts) and raised `max_tokens` (deeper content).

### Current config (prod today)
| component | model | in / out tok | cost |
|---|---|---|---|
| journey skeleton | gpt-4.1-nano | 644 / 582 | 0.030¢ |
| step content × 8 | gpt-4o-mini | 907 / 604 each | 0.050¢ × 8 = 0.40¢ |
| **Total per journey** | | | **≈ 0.43¢** |

### Recommended config (Phases 1–4)
| component | model | in / out tok | cost |
|---|---|---|---|
| journey skeleton (richer contract + context) | **gpt-4.1** | ~1,200 / ~1,200 | 1.20¢ |
| step content × 8 (outline + anchors + deeper output) | **gpt-4.1-mini** | ~2,000 / ~1,400 each | 0.30¢ × 8 = 2.42¢ |
| critic pass × 8 (Phase 4) | gpt-4.1-nano | ~1,700 / ~150 each | 0.023¢ × 8 = 0.18¢ |
| regenerations (~15% fail critic, retried once) | gpt-4.1-mini | 1.2 × step cost | 0.36¢ |
| **Total per journey** | | | **≈ 4.2¢ (~10× current)** |

### Premium options for step content (if 4.1-mini still isn't specific enough on the benchmark)
| step model | per step | per 8-step journey (incl. skeleton + critic) |
|---|---|---|
| gpt-4.1-mini (recommended start) | 0.30¢ | **~4.2¢** |
| gpt-4.1 | 1.52¢ | ~14¢ |
| claude-sonnet-4-6 | 2.70¢ | ~24¢ |

Recommendation: start with gpt-4.1-mini for steps; only escalate the step model if the Phase 0 benchmark still scores low on specificity — and consider escalating *only* for `challenge`/`explore` step types (the two deepest), which would land around **~7¢/journey** instead of 14¢.

### Spark (per call)
| config | model | in / out tok | cost |
|---|---|---|---|
| current | gpt-4.1-nano | 457 / 182 | 0.012¢ |
| proposed | gpt-4.1-mini | ~600 / ~400 | 0.088¢ (~7×, absolute pennies) |
| cheaper alternative | gpt-4o-mini | ~600 / ~400 | 0.033¢ |

`daily_spark` stays on nano — no change, no cost impact. `quiz` is out of scope (already 4o-mini, just re-tuned).

## 4. Monthly projections at scale

Assumes each journey = skeleton + 8 warmed steps + critic; 5 sparks per journey created; recommended config.

| monthly volume | current config | recommended | premium (gpt-4.1 steps) |
|---|---|---|---|
| **Today (≈3 journeys, 1 spark)** | ~$0.001 | **~$0.13** | ~$0.42 |
| 100 journeys + 500 sparks | ~$0.49 | **~$4.60** | ~$14.40 |
| 1,000 journeys + 5,000 sparks | ~$4.90 | **~$46** | ~$144 |
| 10,000 journeys + 50,000 sparks | ~$49 | **~$460** | ~$1,440 |

Context: at 4.2¢/journey, a paying user would need to generate **~200 journeys/month** before AI cost reaches even $8 of a subscription. Content is also cached permanently, so a journey's cost is paid once regardless of how many times its steps are re-read.

## 5. One-time / recurring extras from the plan

| item | volume | cost |
|---|---|---|
| **Phase 0 benchmark run** (20 questions × journey + 3 steps, current + proposed config, + LLM judge on gpt-4.1) | ~40 journeys-equivalent + ~120 judge calls (~2k in / 300 out each) | **~$2.60 per full run** — run at every phase gate, so ~$15 across the project |
| **Phase 4 backfill** — regenerate all existing cached steps at new quality (622 rows in prod) | 622 × 0.30¢ | **~$1.90 one-time** (lazy refresh spreads it over weeks; only actively-viewed journeys regenerate, so real spend is likely a fraction of this) |
| **Phase 4 user "Regenerate step"** | rate-limited 2/step/day, budget-checked | ~0.3¢ per click — bounded by existing `check_budget` |
| **Phase 5 weekly quality report** (judge on ~50 sampled generations) | 50 × ~0.09¢ | ~$0.05/week |
| **Phase 3 structured outputs** | — | slight *saving*: eliminates the double-generation retry in `generate_journey` (currently up to 2× cost on malformed JSON) and parse-failure 502s |

## 6. Cost guardrails already in place (nothing new needed)

- Per-user budgets: every generation path calls `check_budget(uid)` before spending and `record_usage` after — model upgrades don't bypass this; they just consume budget slightly faster.
- Spark session caps (5/hr free tier) and endpoint rate limits (30/min) bound worst-case abuse.
- Prompt-cache discount: OpenAI caches repeated prompt prefixes (the code already tracks `cached_input_tokens`); the long shared style prompts mean effective input cost during a warm burst runs ~25–50% below the table above.
- Rollback is a single `ai_provider_config` UPDATE — if cost spikes unexpectedly, revert models in seconds with no deploy.

## 7. Bottom line

| decision | verdict |
|---|---|
| Upgrade journey to gpt-4.1 | **Do it.** ~1¢/journey for the component that determines all downstream quality. |
| Upgrade step_content to gpt-4.1-mini | **Do it.** ~2.5¢/journey; 10× quality-relevant capability for pennies. |
| Upgrade spark to gpt-4.1-mini | **Do it.** <0.1¢/call; it's the first impression funnel. |
| Step content on gpt-4.1/Sonnet everywhere | **Hold.** 3–6× the recommended cost; decide from Phase 0 benchmark, and if needed apply only to challenge/explore steps. |
| Critic pass + backfill | **Do it.** ~$2 one-time + ~4% overhead per journey. |

The entire quality upgrade, at 10× current volume, costs less than one coffee per month. Cost is not a constraint on this plan until volume approaches ~10k journeys/month — the real constraints are latency (bigger models are slower on the synchronous journey-preview path) and benchmark-verified quality.
