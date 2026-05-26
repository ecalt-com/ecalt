# Graph Report - .  (2026-05-23)

## Corpus Check
- Corpus is ~38,234 words - fits in a single context window. You may not need a graph.

## Summary
- 592 nodes · 1265 edges · 43 communities (31 shown, 12 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 34 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Journey Step Content Tests|Journey Step Content Tests]]
- [[_COMMUNITY_Admin Coupon API Tests|Admin Coupon API Tests]]
- [[_COMMUNITY_Notification & Copy Pipeline|Notification & Copy Pipeline]]
- [[_COMMUNITY_Budget Unit Test Suite|Budget Unit Test Suite]]
- [[_COMMUNITY_AI Journey Generation|AI Journey Generation]]
- [[_COMMUNITY_App Bootstrap & Scheduler|App Bootstrap & Scheduler]]
- [[_COMMUNITY_Chat & AI Provider Layer|Chat & AI Provider Layer]]
- [[_COMMUNITY_Notification Preferences API|Notification Preferences API]]
- [[_COMMUNITY_Mind Signature Pipeline|Mind Signature Pipeline]]
- [[_COMMUNITY_App Routing & Deployment|App Routing & Deployment]]
- [[_COMMUNITY_Admin Panel|Admin Panel]]
- [[_COMMUNITY_Subscriptions & Config|Subscriptions & Config]]
- [[_COMMUNITY_Core Endpoints & Database|Core Endpoints & Database]]
- [[_COMMUNITY_Coupon Budget Unit Tests|Coupon Budget Unit Tests]]
- [[_COMMUNITY_Auth & User Management|Auth & User Management]]
- [[_COMMUNITY_Coupon System|Coupon System]]
- [[_COMMUNITY_Passport & Schema Models|Passport & Schema Models]]
- [[_COMMUNITY_Subscription Budget API Tests|Subscription Budget API Tests]]
- [[_COMMUNITY_Learning Progress Tracking|Learning Progress Tracking]]
- [[_COMMUNITY_Notification DB Schema|Notification DB Schema]]
- [[_COMMUNITY_Migration Runner|Migration Runner]]
- [[_COMMUNITY_Claude Dev Tools|Claude Dev Tools]]
- [[_COMMUNITY_Admin Bootstrap Script|Admin Bootstrap Script]]
- [[_COMMUNITY_Firebase Auth Pattern|Firebase Auth Pattern]]
- [[_COMMUNITY_Logging Config|Logging Config]]
- [[_COMMUNITY_Admin Local Auth|Admin Local Auth]]
- [[_COMMUNITY_Stripe Webhook Handler|Stripe Webhook Handler]]
- [[_COMMUNITY_Coupon Service Module|Coupon Service Module]]
- [[_COMMUNITY_Test Conftest Module|Test Conftest Module]]
- [[_COMMUNITY_Make Admin Module|Make Admin Module]]
- [[_COMMUNITY_Run Migrations Module|Run Migrations Module]]

## God Nodes (most connected - your core abstractions)
1. `get_db()` - 122 edges
2. `mock_db()` - 40 edges
3. `usage()` - 37 edges
4. `extras()` - 37 edges
5. `get_required_user()` - 25 edges
6. `check_budget()` - 22 edges
7. `record_usage()` - 22 edges
8. `apply_coupon()` - 22 edges
9. `get_coupon_extras()` - 20 edges
10. `complete_text()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Python Dependencies (requirements.txt)` --references--> `Provider Service Module`  [INFERRED]
  requirements.txt → app/services/provider_service.py
- `CLAUDE.md Project Developer Reference` --references--> `Provider Service Module`  [INFERRED]
  CLAUDE.md → app/services/provider_service.py
- `Python Dependencies (requirements.txt)` --references--> `Scheduler Service Module`  [INFERRED]
  requirements.txt → app/services/scheduler.py
- `TestJourneyStepContent` --uses--> `JourneyStep`  [INFERRED]
  tests/api/test_api_budget.py → app/models/schemas.py
- `TestSubscriptionMe` --uses--> `JourneyStep`  [INFERRED]
  tests/api/test_api_budget.py → app/models/schemas.py

## Hyperedges (group relationships)
- **FastAPI Auth Dependency Chain** — core_auth_get_optional_user, core_auth_get_required_user, core_auth_get_admin_user [EXTRACTED 1.00]
- **Notification Persistence Schema** — db_table_notification_preferences, db_table_notification_log, db_table_notification_queue [EXTRACTED 1.00]
- **Application Bootstrap Sequence** — app_main, app_main_lifespan, core_logging_config_setup_logging, core_limiter, api_v1_router [EXTRACTED 0.95]
- **Budget Enforcement Pipeline: check -> AI call -> record** — services_subscription_service_check_budget, services_ai_service_generate_journey, services_subscription_service_record_usage [INFERRED 0.95]
- **Post-Chat Background Pipeline: persist + knowledge + usage + cliffhanger** — services_chat_service_post_stream_bg, services_knowledge_service_extract_knowledge_nodes, services_chat_service_queue_cliffhanger [EXTRACTED 1.00]
- **Notification Dispatch: can_send gate + copy generation + channel delivery** — services_notification_service_can_send, services_copy_generator_generate_copy, services_email_service_send_email [INFERRED 0.95]
- **Notification Pipeline: Scheduler enqueues, processor dispatches via notification_service, copy_generator renders AI copy** — services_scheduler_enqueue, services_scheduler_queue_processor, services_copy_generator_generate_copy [INFERRED 0.85]
- **Mind Signature Generation: mastery data drives AI narrative + constellation building + DB storage** — services_mind_signature_service_generate_mind_signature, services_provider_service_complete_text, services_mind_signature_service_build_constellation [EXTRACTED 1.00]
- **Budget Test Suite: unit + integration tests sharing conftest fixtures to validate subscription enforcement** — tests_unit_test_budget_module, tests_api_test_api_budget_module, tests_conftest_mock_db [EXTRACTED 1.00]

## Communities (43 total, 12 thin omitted)

### Community 0 - "Journey Step Content Tests"
Cohesion: 0.07
Nodes (30): Cached content is served for free — no budget check., Cache miss triggers budget check — exhausted budget → 402., On cache miss with budget ok: generates content, records usage, stores in cache., Cached responses should never record usage — they cost nothing., TestJourneyStepContent, apply_coupon(), Apply a coupon to a user. Returns a result dict.     Raises ValueError with a us, get_coupon_extras() (+22 more)

### Community 1 - "Admin Coupon API Tests"
Cohesion: 0.05
Nodes (33): anon_client(), API-level integration tests for budget enforcement.  Tests the HTTP layer: corre, TestClient with no auth overrides — real auth rejects unauthenticated requests., TestAdminCouponEndpoints, TestChatStream, TestCouponApplyEndpoint, TestExplore, get_optional_user() (+25 more)

### Community 2 - "Notification & Copy Pipeline"
Cohesion: 0.06
Nodes (42): client(), TestClient with auth wired to TEST_UID., CLAUDE.md Project Developer Reference, Python Dependencies (requirements.txt), _active_channels(), _channel_status(), get_real_context(), get_user_by_email() (+34 more)

### Community 3 - "Budget Unit Test Suite"
Cohesion: 0.14
Nodes (11): extras(), mock_db_fetchall(), Shared fixtures and helpers for the ECALT test suite., Like mock_db but for fetchall(). Returns lists in sequence., usage(), _patch_budget_deps(), Unit tests for the token budget system.  Scenarios covered:   Free trial / chat, Patch all four sub-functions check_budget() calls internally. (+3 more)

### Community 4 - "AI Journey Generation"
Cohesion: 0.08
Nodes (31): explore(), Submit a curiosity question and receive a fully structured Journey.     Requires, get_step_content(), Returns AI-generated lesson content for a step. Checks cache first., get_my_subscription(), generate_journey(), generate_step_content(), Background task: pre-generate and cache content for all steps in a journey. (+23 more)

### Community 5 - "App Bootstrap & Scheduler"
Cohesion: 0.09
Nodes (36): lifespan(), Catch-all so unhandled exceptions return a proper JSON 500 and CORS     headers, unhandled_exception_handler(), _DevFormatter, _JsonFormatter, setup_logging(), Scheduler Service (setup_scheduler), _active_channel_clause() (+28 more)

### Community 6 - "Chat & AI Provider Layer"
Cohesion: 0.09
Nodes (32): get_ai_config(), Return current provider/model config for each interaction type., get_daily_spark(), get_knowledge_nodes(), _load_conversation(), _persist_messages(), _post_stream_bg(), _queue_cliffhanger() (+24 more)

### Community 7 - "Notification Preferences API"
Cohesion: 0.10
Nodes (29): _ensure_row(), get_preferences(), _normalize_phone(), NotificationPreferences, one_click_unsubscribe(), opt_out_whatsapp(), patch_preferences(), PreferencesPatch (+21 more)

### Community 8 - "Mind Signature Pipeline"
Cohesion: 0.14
Nodes (23): force_generate(), get_my_signature(), Generate unconditionally — useful for manual refresh or testing., Public — no auth required., trigger_generate(), verify_signature(), detect_mastery_boundaries(), get_domain_mastery() (+15 more)

### Community 9 - "App Routing & Deployment"
Cohesion: 0.11
Nodes (17): API v1 Router (api_router), FastAPI Application Entry Point, sitemap_redirect(), build, builder, dockerfilePath, deploy, restartPolicyMaxRetries (+9 more)

### Community 10 - "Admin Panel"
Cohesion: 0.14
Nodes (15): bootstrap_first_admin(), get_admin_user(), get_stats(), get_usage_breakdown(), list_plans(), list_users(), PlanUpdate, Token usage and cost breakdown by model for current billing month. (+7 more)

### Community 11 - "Subscriptions & Config"
Cohesion: 0.16
Nodes (11): BaseSettings, Settings, get_supabase(), CheckoutRequest, create_checkout(), list_plans(), Map Stripe price ID back to our plan_id via plan_configs., Public endpoint: return all active plan configs. (+3 more)

### Community 12 - "Core Endpoints & Database"
Cohesion: 0.20
Nodes (11): Direct psycopg2 Over Supabase SDK Pattern, get_db(), _make_connection(), chat_stream(), delete_conversation(), get_conversation(), list_conversations(), db_check() (+3 more)

### Community 14 - "Auth & User Management"
Cohesion: 0.23
Nodes (12): get_admin_user(), get_required_user(), Verify a Firebase ID token and return the uid on success, None on failure., Like get_optional_user but raises 401 if no valid token., Raises 403 if user is not an admin., _verify_firebase_token(), complete_onboarding(), get_me() (+4 more)

### Community 15 - "Coupon System"
Cohesion: 0.22
Nodes (12): admin_create(), admin_list(), admin_redemptions(), admin_update(), apply(), ApplyRequest, CreateCouponRequest, UpdateCouponRequest (+4 more)

### Community 16 - "Passport & Schema Models"
Cohesion: 0.23
Nodes (11): BaseModel, AIConfigUpdate, BootstrapRequest, ChatRequest, get_passport(), PassportJourney, PassportResponse, Return the authenticated user's full capability passport. (+3 more)

### Community 18 - "Learning Progress Tracking"
Cohesion: 0.25
Nodes (10): get_progress(), JourneyProgressResponse, mark_step_complete(), mark_step_incomplete(), ProgressResponse, Increment streak if a new day, reset if gap, no-op if same day. Best-effort., Return all completed step IDs for a journey., Mark a step as complete. Idempotent. Updates daily streak. (+2 more)

### Community 19 - "Notification DB Schema"
Cohesion: 0.33
Nodes (7): Notification Channel Architecture (email + WhatsApp), WhatsApp Opt-in Flow, notification_log Table, notification_preferences Table, notification_queue Table, Add Notification Log and Queue Migration, Add Notification Preferences Migration

### Community 20 - "Migration Runner"
Cohesion: 0.48
Nodes (6): applied_set(), apply_file(), connect(), ensure_tracking_table(), main(), Apply SQL migrations under backend/migrations/ to Supabase.  Reads credentials f

## Knowledge Gaps
- **34 isolated node(s):** `$schema`, `builder`, `dockerfilePath`, `startCommand`, `restartPolicyType` (+29 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_db()` connect `Core Endpoints & Database` to `Journey Step Content Tests`, `Admin Coupon API Tests`, `Notification & Copy Pipeline`, `AI Journey Generation`, `App Bootstrap & Scheduler`, `Chat & AI Provider Layer`, `Notification Preferences API`, `Mind Signature Pipeline`, `Admin Panel`, `Subscriptions & Config`, `Auth & User Management`, `Coupon System`, `Passport & Schema Models`, `Learning Progress Tracking`?**
  _High betweenness centrality (0.538) - this node is a cross-community bridge._
- **Why does `check_budget()` connect `AI Journey Generation` to `Journey Step Content Tests`, `Admin Coupon API Tests`, `Budget Unit Test Suite`, `Core Endpoints & Database`, `Coupon Budget Unit Tests`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `mock_db()` connect `Journey Step Content Tests` to `Admin Coupon API Tests`, `Budget Unit Test Suite`, `Subscription Budget API Tests`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `get_db()` (e.g. with `Direct psycopg2 Over Supabase SDK Pattern` and `get_supabase()`) actually correct?**
  _`get_db()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `$schema`, `builder`, `dockerfilePath` to the rest of the system?**
  _150 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Journey Step Content Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.06861239119303636 - nodes in this community are weakly interconnected._
- **Should `Admin Coupon API Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.05446853516657853 - nodes in this community are weakly interconnected._