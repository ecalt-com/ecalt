# ECALT — Implementation Tasks

> Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 1 — Conversation Interface Foundation
**Goal:** Transform from step-based journeys to flowing 3-panel conversation. `/learn` becomes primary experience.

### 1A — Database Schema
- [ ] Append to `supabase_schema.sql`: ALTER users (streak_days, last_active_date)
- [ ] Add `user_interests` table
- [ ] Add `conversations` table
- [ ] Add `conversation_messages` table
- [ ] Add `knowledge_nodes` table
- [ ] Add `daily_sparks` table
- [ ] Add indexes for all new tables
- [ ] Run migrations in Supabase dashboard

### 1B — Backend: Chat Service
- [ ] Create `backend/app/services/chat_service.py`
  - [ ] `build_safe_prompt(ctx)` — structured content blocks, never string concat
  - [ ] `validate_output(response)` — block injection patterns
  - [ ] `route_model(interaction_type)` — Haiku for daily/nudge, Sonnet for onboarding/fingerprint/mind_signature
  - [ ] `stream_chat(conversation_id, message, uid)` — yields SSE chunks, saves to DB, extracts nodes async
- [ ] Create `backend/app/services/knowledge_service.py`
  - [ ] `extract_knowledge_nodes(conversation_text, uid)` — Haiku-powered extraction, upsert into knowledge_nodes
- [ ] Update `backend/app/services/spark_service.py`
  - [ ] Add `generate_daily_spark(uid, topics)` — cached per-user per-day

### 1C — Backend: Endpoints
- [ ] Create `backend/app/api/v1/endpoints/chat.py`
  - [ ] `POST /api/v1/chat/stream` — SSE stream (auth required)
  - [ ] `GET /api/v1/chat/conversations` — list user's conversations
  - [ ] `GET /api/v1/chat/conversations/{id}` — messages for a conversation
  - [ ] `DELETE /api/v1/chat/conversations/{id}`
- [ ] Create `backend/app/api/v1/endpoints/knowledge.py`
  - [ ] `GET /api/v1/knowledge/nodes` — user's knowledge nodes
  - [ ] `GET /api/v1/knowledge/spark` — today's spark prompt
- [ ] Update `backend/app/api/v1/router.py` — include chat + knowledge routers

### 1D — Frontend: 3-Panel Learn Page
- [ ] Create `frontend/src/pages/Learn.tsx` — 3-panel layout (25/50/25 split)
- [ ] Create `frontend/src/components/learn/TodaysSpark.tsx`
  - [ ] Fetches `GET /api/v1/knowledge/spark`
  - [ ] "Start exploring →" click populates + sends conversation input
- [ ] Create `frontend/src/components/learn/ConversationInterface.tsx`
  - [ ] SSE streaming via fetch + ReadableStream
  - [ ] Real-time markdown rendering as chunks arrive
  - [ ] Auto-scroll to bottom on new chunks
  - [ ] Input bar at bottom with send button
  - [ ] Image upload icon (stub — hidden for free accounts)
- [ ] Create `frontend/src/components/learn/KnowledgeUniverse.tsx`
  - [ ] Phase 1: tag cloud of knowledge_nodes, sized by strength
  - [ ] Polls after each assistant message
- [ ] Create `frontend/src/components/learn/WarmthIndicator.tsx`
  - [ ] Subtle strip at top of center panel
  - [ ] 0 msgs: neutral gray → 3+ msgs: violet glow → 7+ msgs: amber warmth
- [ ] Update `frontend/src/App.tsx` — add `/learn` route, redirect post-auth to `/learn`
- [ ] Update `frontend/src/lib/api.ts` — add `streamChat`, `getConversations`, `getKnowledgeNodes`, `getDailySpark`

### 1E — Phase 1 Verification
- [ ] Sign in → lands on `/learn`
- [ ] TodaysSpark shows a prompt
- [ ] Click spark → conversation starts, response streams in real-time
- [ ] Right panel updates with new knowledge nodes after exchange
- [ ] Warmth indicator transitions correctly
- [ ] No lesson numbers, no progress bars, no chapter titles anywhere

---

## Phase 2 — Subscription & Token Budget System
**Goal:** Stripe billing for 6 plan tiers, token budget enforcement, admin pricing panel.

### 2A — Database Schema
- [ ] Add `plan_configs` table with default plan rows
- [ ] Add `subscriptions` table
- [ ] Add `token_usage` table
- [ ] ALTER users: add `is_admin` boolean column
- [ ] Run migrations in Supabase

### 2B — Backend: Subscription Service
- [ ] Create `backend/app/services/subscription_service.py`
  - [ ] `get_user_plan(uid)` — fetch plan, default to free_trial
  - [ ] `check_token_budget(uid)` → `(allowed, used_cents, budget_cents)`
  - [ ] `record_token_usage(uid, input_tokens, output_tokens, model)` — cost calc by model
  - [ ] `check_lifetime_messages(uid)` — block free_trial at 6 messages
  - [ ] `create_stripe_checkout(uid, plan_id)` → checkout session URL
  - [ ] `handle_stripe_webhook(payload, sig_header)` — upsert subscription on events
- [ ] Create `backend/app/core/budget_middleware.py`
  - [ ] Applied to `/api/v1/chat/stream` before AI call
  - [ ] Returns 402 + `{error, upgrade_url}` if over budget/limit
- [ ] Update `backend/app/core/config.py` — add STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
- [ ] Install `stripe` Python package

### 2C — Backend: Endpoints
- [ ] Create `backend/app/api/v1/endpoints/subscriptions.py`
  - [ ] `GET /api/v1/subscriptions/me`
  - [ ] `POST /api/v1/subscriptions/checkout` — create Stripe checkout session
  - [ ] `POST /api/v1/subscriptions/webhook` — Stripe webhook handler
- [ ] Create `backend/app/api/v1/endpoints/admin.py`
  - [ ] `GET /api/v1/admin/plans`
  - [ ] `PATCH /api/v1/admin/plans/{plan_id}` — adjust price/budget
  - [ ] `GET /api/v1/admin/stats` — DAU, messages, revenue estimate
- [ ] Update `backend/app/api/v1/router.py` — include subscriptions + admin routers

### 2D — Frontend
- [ ] Create `frontend/src/lib/SubscriptionContext.tsx` — fetches plan on auth, exposes plan/budget
- [ ] Create `frontend/src/pages/Pricing.tsx` — 6-tier pricing cards
- [ ] Create `frontend/src/pages/Admin.tsx` — admin-only pricing + stats panel
- [ ] Create `frontend/src/components/UpgradePrompt.tsx` — inline 402 handler
- [ ] Update `frontend/src/App.tsx` — add `/pricing` and `/admin` routes
- [ ] Add `VITE_STRIPE_PUBLISHABLE_KEY` to frontend env

### 2E — Phase 2 Verification
- [ ] New user sees free_trial plan (6 message limit)
- [ ] 6th message → UpgradePrompt appears, no further messages
- [ ] Upgrade → Stripe checkout → webhook → subscription active
- [ ] After upgrade, limit removed, token budget tracked
- [ ] Admin (`is_admin=true`) visits `/admin` → edits plan prices live
- [ ] Price change reflects immediately for new checkouts

---

## Phase 3 — Mind Signature
**Goal:** D3.js constellation visualization of cognitive capability at mastery boundaries.

### 3A — Database Schema
- [ ] Add `domain_mastery` table
- [ ] Add `mind_signatures` table with verification_hash index
- [ ] Run migrations in Supabase

### 3B — Backend: Mastery + Mind Signature Services
- [ ] Create `backend/app/services/mastery_service.py`
  - [ ] `update_domain_mastery(uid)` — recalculate from knowledge_nodes grouped by domain
  - [ ] `detect_mastery_boundary(uid)` — returns qualifying domains (mastery ≥ 0.75, concepts ≥ 8)
  - [ ] `should_generate_signature(uid)` — true if boundary detected + no signature in 7 days
- [ ] Create `backend/app/services/mind_signature_service.py`
  - [ ] `generate_mind_signature(uid)` — full pipeline:
    1. Fetch domain_mastery
    2. Build constellation_data (nodes + links)
    3. Call Sonnet → 3-paragraph capability_narrative
    4. SHA-256 verification_hash
    5. Store + return MindSignature

### 3C — Backend: Endpoints
- [ ] Create `backend/app/api/v1/endpoints/mind_signature.py`
  - [ ] `GET /api/v1/mind-signature/me`
  - [ ] `POST /api/v1/mind-signature/generate`
  - [ ] `GET /api/v1/verify/{hash}` — public, no auth
- [ ] Update `backend/app/api/v1/router.py` — include mind_signature router

### 3D — Frontend: Constellation
- [ ] Install `d3` + `@types/d3` in frontend
- [ ] Create `frontend/src/components/constellation/ConstellationMap.tsx`
  - [ ] D3 force-directed graph
  - [ ] Nodes: domains, radius = mastery * 40 + 10, brightness = concept_count
  - [ ] Links: shared concepts, thickness = overlap count
  - [ ] Animated pulse + shimmer on links
  - [ ] Colors: violet → cyan → amber (design tokens)
  - [ ] Hover tooltip: domain, concept count, mastery %
  - [ ] SVG, responsive via ResizeObserver
- [ ] Create `frontend/src/pages/MindSignature.tsx`
  - [ ] Full constellation + capability narrative + domain depth indicators
  - [ ] Emergence zones (high learning_velocity domains highlighted)
  - [ ] Verification hash with copy button
  - [ ] LinkedIn/Twitter share button
- [ ] Create `frontend/src/pages/Verify.tsx` — public verification at `/verify/:hash`
- [ ] Update `frontend/src/components/learn/KnowledgeUniverse.tsx`
  - [ ] Mini constellation preview when signatures exist
  - [ ] "View Mind Signature" link
- [ ] Update `frontend/src/App.tsx` — add `/mind-signature` + `/verify/:hash` routes

### 3E — Phase 3 Verification
- [ ] User with 8+ nodes across domains → `POST /mind-signature/generate` succeeds
- [ ] Constellation renders with correct nodes + connections
- [ ] Capability narrative: coherent 3 paragraphs
- [ ] `/verify/:hash` resolves publicly, no login required
- [ ] KnowledgeUniverse shows mini constellation + link

---

## Phase 4 — Image Upload + Security Polish
**Goal:** Haiku vision for enrolled users; prompt injection hardening across all AI calls.

### 4A — Prompt Injection Defense
- [ ] Update `chat_service.py` — enforce `build_safe_prompt` + `validate_output` for all calls
- [ ] Update `ai_service.py` — same structured content blocks
- [ ] Update `spark_service.py` — same structured content blocks
- [ ] Update `mind_signature_service.py` — same structured content blocks
- [ ] Verify: send `"ignore previous instructions"` → safe default response returned

### 4B — Image Upload
- [ ] Update `backend/app/services/chat_service.py`
  - [ ] Add `vision_chat(conversation_id, message, image_base64, uid)` path
  - [ ] Force Haiku 4.5 vision model
  - [ ] Gated: subscription plan != `free_trial`
- [ ] Update `backend/app/api/v1/endpoints/chat.py`
  - [ ] Accept optional `image` (base64) in `POST /chat/stream` body
  - [ ] Validate: max 5MB, JPEG/PNG/GIF/WEBP only
- [ ] Create `frontend/src/components/learn/ImageUploadButton.tsx`
  - [ ] Hidden/disabled for free_trial (tooltip: "Image analysis for enrolled users")
  - [ ] File selection, 5MB validation, preview thumbnail
- [ ] Update `frontend/src/components/learn/ConversationInterface.tsx`
  - [ ] Wire up ImageUploadButton
  - [ ] Show thumbnail before send, show "Image attached" after send

### 4C — Security Headers
- [ ] Update `frontend/vercel.json` — add CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- [ ] Update `backend/app/main.py` — add HSTS middleware

### 4D — Phase 4 Verification
- [ ] Free user: image icon visible but disabled with tooltip
- [ ] Enrolled user: upload → thumbnail → sends → Haiku vision responds about image
- [ ] Prompt injection test passes
- [ ] `curl -I https://ecalt.vercel.app` shows security headers

---

## New Dependencies Checklist
- [ ] Backend: `pip install stripe` (Phase 2)
- [ ] Frontend: `npm install d3 @types/d3` (Phase 3)

## Env Vars Checklist
- [ ] Railway: `STRIPE_SECRET_KEY`
- [ ] Railway: `STRIPE_WEBHOOK_SECRET`
- [ ] Railway: `STRIPE_PUBLISHABLE_KEY`
- [ ] Vercel: `VITE_STRIPE_PUBLISHABLE_KEY`
