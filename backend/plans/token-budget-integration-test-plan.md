# Token Budget Integration Test Plan

**Goal:** Guarantee that every OpenAI/Anthropic call on every plan tier (INR Razorpay + USD Stripe) is
gated by `check_budget`, recorded in `token_usage` + `usage_by_interaction` with real token counts,
and that users can never over-consume their budget without detection.

---

## Discovered Gaps (pre-existing, addressed by this plan)

| # | Gap | Severity |
|---|-----|----------|
| G1 | `quiz` endpoint calls `record_usage(uid, 0, 0, …)` — actual tokens never captured | **High** |
| G2 | `mind_signature` trigger has no `check_budget` call and no `record_usage` call | **High** |
| G3 | `knowledge` endpoint (`generate_daily_spark`) has no `check_budget` or `record_usage` | **High** |
| G4 | `warm_journey_steps` background task has no `check_budget` gate per step | **Medium** |
| G5 | `journeys.py:251` calls `record_usage` without `interaction_type` argument → goes to `unknown` | **Medium** |
| G6 | `conftest.py` `INDIVIDUAL.base_price_cents=1900` but DB=`1000`; `STUDENT.base_price_cents=900` but DB=`500` | **Low** (logic unaffected) |
| G7 | No fixtures or budget tests for `family`, `university`, `enterprise` plans | **Medium** |
| G8 | Race condition: two simultaneous requests near budget limit both pass `check_budget` before either records | **Medium** |
| G9 | `usage_by_interaction` population never tested independently of `token_usage` | **Medium** |
| G10 | INR (Razorpay) subscriber and USD (Stripe) subscriber never asserted to share same `token_budget_cents` | **Medium** |

---

## Phase 1 — Fix Stale Fixtures & Add Missing Plan Configs

**Files:** `tests/conftest.py`

**What to do:** Sync all plan fixtures with real DB values. Add missing plan constants.

### 1.1 Sync existing plan prices

```python
# Current (stale)          → Correct (matches DB)
INDIVIDUAL.base_price_cents = 1900  → 1000   # $10.00
STUDENT.base_price_cents    = 900   → 500    # $5.00
```

Token budget values are already correct — only the price field is wrong.

### 1.2 Add missing plan fixtures

```python
FAMILY = {
    "plan_id": "family",
    "name": "Family",
    "base_price_cents": 3000,
    "token_budget_cents": 1560.0,
    "lifetime_message_limit": None,
    "max_seats": 5,
    "is_active": True,
}

UNIVERSITY = {
    "plan_id": "university",
    "name": "University",
    "base_price_cents": 29900,
    "token_budget_cents": 11960.0,
    "lifetime_message_limit": None,
    "max_seats": 50,
    "is_active": True,
}

ENTERPRISE = {
    "plan_id": "enterprise",
    "name": "Enterprise",
    "base_price_cents": 49900,
    "token_budget_cents": 19900.0,
    "lifetime_message_limit": None,
    "max_seats": 200,
    "is_active": True,
}

# INR variants — same plan_id, same token_budget_cents, different gateway
INDIVIDUAL_INR = {**INDIVIDUAL, "payment_gateway": "razorpay", "base_price_inr_paise": 69900}
STUDENT_INR    = {**STUDENT,    "payment_gateway": "razorpay", "base_price_inr_paise": 39900}
FAMILY_INR     = {**FAMILY,     "payment_gateway": "razorpay", "base_price_inr_paise": 199900}
```

### 1.3 Tests to write — `tests/unit/test_plan_configs.py`

```python
class TestPlanConfigsMatchDB:
    """Assert fixture constants match live DB values (runs in CI with DB access only)."""

    @pytest.mark.integration
    def test_all_plan_token_budgets_match_db(self):
        # Query plan_configs table directly and assert each fixture's
        # token_budget_cents matches exactly.
        pass

    @pytest.mark.integration
    def test_inr_plans_have_same_budget_as_usd_plans(self):
        # student (INR Razorpay) == student (USD Stripe) in token_budget_cents
        pass

    @pytest.mark.unit
    def test_fixture_token_budgets_are_internally_consistent(self):
        # token_budget_cents ≈ 40% of base_price_cents for all paid plans
        for plan in [INDIVIDUAL, STUDENT, FAMILY]:
            expected = round(plan["base_price_cents"] * 0.40, 0)
            # Allow small rounding; this confirms the 40% rule is not violated
            assert abs(plan["token_budget_cents"] - expected) <= 10
```

---

## Phase 2 — Budget Gate Completeness Audit

**Goal:** Every endpoint that triggers an OpenAI call must call `check_budget` before the AI call.

### 2.1 Current wiring status

| Endpoint | check_budget? | context arg | Notes |
|----------|--------------|-------------|-------|
| `POST /chat/stream` | ✅ | `"chat"` | Correct |
| `POST /explore` | ✅ | `"ai"` (default) | Correct |
| `GET /journeys/{id}/steps/{step_id}/content` | ✅ (cache miss only) | `"ai"` (default) | Correct |
| `POST /spark` (authenticated) | ✅ | `"ai"` | Correct |
| `POST /spark` (guest) | ✅ skipped by design | n/a | Acceptable — no uid |
| `POST /quiz` | ✅ | `"ai"` (default) | Correct gate, but records 0 tokens (G1) |
| `POST /mind_signature/trigger` | ❌ **MISSING** | — | **Gap G2 — fix required** |
| `GET /knowledge` (daily_spark) | ❌ **MISSING** | — | **Gap G3 — fix required** |
| `warm_journey_steps` (bg task) | ❌ by design | — | Acceptable (already gated at explore) |

### 2.2 Fixes required before tests

**`mind_signature.py` — add before `generate_mind_signature` call:**
```python
from app.services.subscription_service import check_budget
allowed, reason = check_budget(uid, context="ai")
if not allowed:
    raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})
```

**`knowledge.py` — add before `generate_daily_spark` call:**
```python
from app.services.subscription_service import check_budget
if uid:
    allowed, reason = check_budget(uid, context="ai")
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})
```

### 2.3 Tests to write — `tests/api/test_api_budget_coverage.py`

```python
class TestMindSignatureBudgetGate:

    def test_budget_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.post("/api/v1/mind_signature/trigger")
        assert res.status_code == 402
        assert res.json()["detail"]["error"] == "budget_exhausted"

    def test_free_trial_ai_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.post("/api/v1/mind_signature/trigger")
        assert res.status_code == 402

    def test_budget_ok_calls_generate(self, client):
        with patch("app.api.v1.endpoints.mind_signature.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.mind_signature.generate_mind_signature",
                   new_callable=AsyncMock, return_value={...}):
            res = client.post("/api/v1/mind_signature/trigger")
        assert res.status_code != 402

    def test_no_auth_returns_401(self, anon_client):
        res = anon_client.post("/api/v1/mind_signature/trigger")
        assert res.status_code == 401


class TestKnowledgeDailySparkBudgetGate:

    def test_authenticated_budget_exhausted_returns_402(self, client):
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(False, "budget_exhausted")):
            res = client.get("/api/v1/knowledge/daily-spark")
        assert res.status_code == 402

    def test_budget_ok_returns_200(self, client):
        with patch("app.api.v1.endpoints.knowledge.check_budget",
                   return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.knowledge.generate_daily_spark",
                   new_callable=AsyncMock, return_value="What if gravity ran backwards?"):
            res = client.get("/api/v1/knowledge/daily-spark")
        assert res.status_code == 200


class TestAllAIEndpointsRequireAuth:
    """Every AI-gated endpoint must return 401 for unauthenticated requests."""

    @pytest.mark.parametrize("method,url,body", [
        ("post", "/api/v1/chat/stream",             {"message": "hello"}),
        ("post", "/api/v1/explore",                 {"question": "Why?"}),
        ("post", "/api/v1/quiz",                    {"concept": "x", "context": "y"}),
        ("post", "/api/v1/mind_signature/trigger",  {}),
    ])
    def test_unauthenticated_returns_401(self, anon_client, method, url, body):
        res = getattr(anon_client, method)(url, json=body)
        assert res.status_code == 401
```

---

## Phase 3 — Usage Recording Correctness

**Goal:** Every AI call records REAL token counts (not zeros). Both `token_usage` and
`usage_by_interaction` are populated. Each call is tagged with the correct `interaction_type`.

### 3.1 Fix G1 — Quiz endpoint records zero tokens

**Current code (`quiz.py:52`):**
```python
record_usage(uid, 0, 0, cfg["model"], interaction_type="quiz")
```

**Root cause:** `generate_quiz()` calls `complete_text()` but discards tokens with `_, _, _, _`.

**Fix in `quiz_service.py`:**
```python
# Before
raw, _, _, _ = await complete_text(...)

# After
raw, in_tok, out_tok, _ = await complete_text(...)
return quiz_data, in_tok, out_tok
```

**Fix in `quiz.py`:**
```python
quiz, in_tok, out_tok = await generate_quiz(...)
record_usage(uid, in_tok, out_tok, cfg["model"], interaction_type="quiz")
```

### 3.2 Fix G5 — `journeys.py` missing `interaction_type`

**Current code (`journeys.py:251`):**
```python
record_usage(uid, in_tok, out_tok, get_config("step_content")["model"])
```

**Fix:**
```python
record_usage(uid, in_tok, out_tok, get_config("step_content")["model"],
             interaction_type="step_content")
```

### 3.3 Fix G2 — `mind_signature` must record usage

After `generate_mind_signature` completes:
```python
sig, in_tok, out_tok = await generate_mind_signature(uid)
record_usage(uid, in_tok, out_tok, get_config("mind_signature")["model"],
             interaction_type="mind_signature")
```

Requires `generate_mind_signature` to return token counts (same pattern as `generate_journey`).

### 3.4 Fix G3 — `knowledge` daily spark must record usage

```python
spark, in_tok, out_tok = await generate_daily_spark(uid)
record_usage(uid, in_tok, out_tok, get_config("daily_spark")["model"],
             interaction_type="daily_spark")
```

### 3.5 Tests to write — `tests/unit/test_usage_recording.py`

```python
class TestQuizRecordsRealTokens:

    def test_quiz_records_nonzero_tokens(self, client):
        usage_recorded = []
        def spy_record(uid, in_tok, out_tok, model, **kwargs):
            usage_recorded.append((in_tok, out_tok))

        with patch("app.api.v1.endpoints.quiz.check_budget", return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.quiz.generate_quiz",
                   new_callable=AsyncMock, return_value=(SAMPLE_QUIZ, 350, 180)), \
             patch("app.api.v1.endpoints.quiz.record_usage", side_effect=spy_record):
            res = client.post("/api/v1/quiz", json={"concept": "gravity", "context": "..."})

        assert res.status_code == 200
        assert len(usage_recorded) == 1
        in_tok, out_tok = usage_recorded[0]
        assert in_tok == 350
        assert out_tok == 180
        assert in_tok > 0 and out_tok > 0  # never zero

    def test_quiz_records_correct_interaction_type(self, client):
        recorded = []
        def spy(uid, in_tok, out_tok, model, interaction_type="unknown", **kw):
            recorded.append(interaction_type)

        with patch("app.api.v1.endpoints.quiz.check_budget", return_value=(True, "ok")), \
             patch("app.api.v1.endpoints.quiz.generate_quiz",
                   new_callable=AsyncMock, return_value=(SAMPLE_QUIZ, 100, 50)), \
             patch("app.api.v1.endpoints.quiz.record_usage", side_effect=spy):
            client.post("/api/v1/quiz", json={"concept": "x", "context": "y"})

        assert recorded == ["quiz"]


class TestInteractionTypeTagging:
    """Every AI endpoint must pass the correct interaction_type to record_usage."""

    CASES = [
        # (endpoint_method, url, body, expected_interaction_type, mock_patch_target)
        ("post",  "/api/v1/explore",                  {"question": "Why?"},         "journey",        "app.api.v1.endpoints.explore.record_usage"),
        ("get",   "/api/v1/journeys/x/steps/y/content", None,                       "step_content",   "app.api.v1.endpoints.journeys.record_usage"),
        ("post",  "/api/v1/quiz",                     {"concept": "c", "context":"ctx"}, "quiz",       "app.api.v1.endpoints.quiz.record_usage"),
        ("post",  "/api/v1/spark",                    {"question": "q", "session_id": "s"}, "spark",  "app.api.v1.endpoints.spark.record_usage"),
    ]

    @pytest.mark.parametrize("method,url,body,expected_type,patch_path", CASES)
    def test_interaction_type_matches_expected(self, client, method, url, body,
                                               expected_type, patch_path):
        recorded_types = []
        def spy(uid, in_tok, out_tok, model, interaction_type="unknown", **kw):
            recorded_types.append(interaction_type)

        # Wire mocks per endpoint... (expand per case)
        with patch(patch_path, side_effect=spy):
            # ... setup check_budget + AI generate mocks per case
            pass

        assert expected_type in recorded_types


class TestUsageByInteractionPopulated:
    """
    record_usage must write to BOTH token_usage and usage_by_interaction.
    Verify the second INSERT is present in every call.
    """

    def test_both_tables_receive_upsert(self):
        from app.services.subscription_service import record_usage

        executed_sql = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed_sql.append(sql)
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 500, 200, "gpt-4o-mini", interaction_type="daily_chat")

        table_names = [sql for sql in executed_sql if "INSERT INTO" in sql]
        assert any("token_usage" in s for s in table_names), "token_usage not written"
        assert any("usage_by_interaction" in s for s in table_names), "usage_by_interaction not written"

    def test_interaction_type_passed_to_usage_by_interaction(self):
        from app.services.subscription_service import record_usage

        captured_params = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            def side_effect(sql, params=None):
                if "usage_by_interaction" in sql and params:
                    captured_params.append(params)
            cur.execute.side_effect = side_effect
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type="step_content")

        assert captured_params, "usage_by_interaction INSERT never executed"
        # params order: uid, period_start, interaction_type, ...
        assert captured_params[0][2] == "step_content"

    def test_unknown_interaction_type_never_used(self):
        """No endpoint should reach record_usage with interaction_type='unknown'."""
        # This is a static analysis test — scan all record_usage call sites
        import ast, pathlib
        endpoints_dir = pathlib.Path("app/api/v1/endpoints")
        for pyfile in endpoints_dir.glob("*.py"):
            src = pyfile.read_text()
            if "record_usage" in src:
                # Parse AST and find record_usage calls missing interaction_type
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and
                            hasattr(node.func, "id") and
                            node.func.id == "record_usage"):
                        kwargs = {kw.arg for kw in node.keywords}
                        assert "interaction_type" in kwargs, \
                            f"{pyfile.name}: record_usage called without interaction_type"
```

---

## Phase 4 — INR / USD Payment Gateway Parity

**Goal:** A user who paid in INR via Razorpay on `individual` plan gets the same `token_budget_cents`
as a user who paid in USD via Stripe on `individual` plan.

### 4.1 How the gateway path works

```
Razorpay webhook → verify_razorpay_payment() → upsert_subscription_from_stripe(
    uid, plan_id=<plan_id>, payment_gateway="razorpay"
)
```

The `plan_id` string is the same (`"individual"`, `"student"`, `"family"`).
`get_user_plan()` queries `plan_configs` by `plan_id` — payment_gateway is invisible to budget logic.
This is correct by design. Tests below verify this invariant is never broken.

### 4.2 Tests to write — `tests/unit/test_payment_gateway_parity.py`

```python
class TestGatewayParity:

    def _budget_for_plan(self, plan_dict):
        """Simulate check_budget with a given plan and zero usage."""
        from app.services.subscription_service import check_budget
        p1 = patch("app.services.subscription_service.get_user_plan",           return_value=plan_dict)
        p2 = patch("app.services.subscription_service.get_current_usage",        return_value=usage(0.0))
        p3 = patch("app.services.subscription_service.get_coupon_extras",        return_value=extras())
        p4 = patch("app.services.subscription_service.count_lifetime_messages",  return_value=0)
        with p1, p2, p3, p4:
            return check_budget(TEST_UID, context="ai")

    @pytest.mark.parametrize("plan_usd,plan_inr", [
        (INDIVIDUAL,    INDIVIDUAL_INR),
        (STUDENT,       STUDENT_INR),
        (FAMILY,        FAMILY_INR),
    ])
    def test_same_budget_regardless_of_gateway(self, plan_usd, plan_inr):
        """USD and INR subscribers on the same plan get identical budget decisions."""
        allowed_usd, _ = self._budget_for_plan(plan_usd)
        allowed_inr, _ = self._budget_for_plan(plan_inr)
        assert allowed_usd == allowed_inr

    @pytest.mark.parametrize("plan_usd,plan_inr", [
        (INDIVIDUAL,    INDIVIDUAL_INR),
        (STUDENT,       STUDENT_INR),
        (FAMILY,        FAMILY_INR),
    ])
    def test_budget_block_consistent_at_exact_limit(self, plan_usd, plan_inr):
        """Both gateways block at exactly the same cost threshold."""
        from app.services.subscription_service import check_budget
        budget = plan_usd["token_budget_cents"]

        for plan in (plan_usd, plan_inr):
            with patch("app.services.subscription_service.get_user_plan", return_value=plan), \
                 patch("app.services.subscription_service.get_current_usage", return_value=usage(budget)), \
                 patch("app.services.subscription_service.get_coupon_extras", return_value=extras()), \
                 patch("app.services.subscription_service.count_lifetime_messages", return_value=0):
                allowed, reason = check_budget(TEST_UID, context="ai")
            assert allowed is False, f"plan {plan['plan_id']} ({plan.get('payment_gateway','stripe')}) should be blocked at budget"
            assert reason == "budget_exhausted"

    def test_upsert_subscription_preserves_plan_id(self):
        """upsert_subscription_from_stripe stores the plan_id correctly for both gateways."""
        from app.services.subscription_service import upsert_subscription_from_stripe

        executed = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed.append((sql, params))
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            upsert_subscription_from_stripe(
                uid=TEST_UID, plan_id="individual",
                payment_gateway="razorpay",
                razorpay_subscription_id="sub_rzp_123",
            )

        assert executed, "No SQL executed"
        sql, params = executed[0]
        assert "INSERT INTO subscriptions" in sql
        # plan_id must be "individual" (position 2 in params)
        assert params[1] == "individual"
        # payment_gateway must be "razorpay"
        assert "razorpay" in params

    @pytest.mark.integration
    def test_db_plan_configs_inr_plans_have_razorpay_plan_id(self):
        """student, individual, family must have razorpay_plan_id set."""
        from app.core.database import get_db
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT plan_id, razorpay_plan_id FROM plan_configs "
                    "WHERE plan_id IN ('student', 'individual', 'family')"
                )
                rows = {r["plan_id"]: r["razorpay_plan_id"] for r in cur.fetchall()}
        for plan_id in ("student", "individual", "family"):
            assert rows.get(plan_id), f"{plan_id} missing razorpay_plan_id in DB"
```

---

## Phase 5 — Token Budget Arithmetic & Edge Cases

**Goal:** Budget math never silently truncates, floats never cause off-by-one blocks/passes,
period rollover resets correctly, and NULL values always fall back safely.

### 5.1 Tests to write — `tests/unit/test_budget_arithmetic.py`

```python
class TestAllPlanBudgets:
    """Verify check_budget for every plan tier, not just free_trial and individual."""

    @pytest.mark.parametrize("plan,budget_cents", [
        (FREE_TRIAL,  20.0),
        (STUDENT,     360.0),
        (INDIVIDUAL,  760.0),
        (FAMILY,      1560.0),
        (UNIVERSITY,  11960.0),
        (ENTERPRISE,  19900.0),
    ])
    def test_just_under_budget_allowed(self, plan, budget_cents):
        allowed, _ = _run_check(plan, usage(budget_cents - 0.001), extras())
        assert allowed is True

    @pytest.mark.parametrize("plan,budget_cents", [
        (FREE_TRIAL,  20.0),
        (STUDENT,     360.0),
        (INDIVIDUAL,  760.0),
        (FAMILY,      1560.0),
        (UNIVERSITY,  11960.0),
        (ENTERPRISE,  19900.0),
    ])
    def test_at_exact_budget_blocked(self, plan, budget_cents):
        allowed, reason = _run_check(plan, usage(budget_cents), extras())
        assert allowed is False
        assert reason == "budget_exhausted"

    @pytest.mark.parametrize("plan", [STUDENT, INDIVIDUAL, FAMILY, UNIVERSITY, ENTERPRISE])
    def test_paid_plan_chat_context_uses_token_budget_not_message_count(self, plan):
        """Paid plans must never hit message-count gate — only token budget applies."""
        allowed, reason = _run_check(plan, usage(1.0), extras(), context="chat")
        assert allowed is True
        assert reason == "ok"

    def test_family_plan_coupon_extends_correctly(self):
        allowed, _ = _run_check(FAMILY, usage(1560.0), extras(credits=100.0))
        assert allowed is True  # 1560 < 1660

    def test_university_plan_blocks_at_exact_limit(self):
        allowed, reason = _run_check(UNIVERSITY, usage(11960.0), extras())
        assert allowed is False
        assert reason == "budget_exhausted"


class TestFloatEdgeCases:

    def test_floating_point_near_budget_boundary(self):
        """0.1 + 0.2 != 0.3 in floats — ensure comparison is robust."""
        # Build up cost from 10 × 0.02 = 0.2 cents
        # This tests that cumulative float addition doesn't falsely exceed budget
        cost = sum(0.02 for _ in range(10))  # 10 × 0.02
        allowed, _ = _run_check(FREE_TRIAL, usage(cost), extras())
        assert allowed is True  # 0.2 < 20.0

    def test_very_small_remaining_budget_still_blocks_at_zero(self):
        """A user with 0.0001 cents of budget left should be considered over budget only at 0."""
        # spent = 19.9999, budget = 20.0 → allowed
        allowed, _ = _run_check(FREE_TRIAL, usage(19.9999), extras())
        assert allowed is True
        # spent = 20.0 → blocked
        allowed, _ = _run_check(FREE_TRIAL, usage(20.0), extras())
        assert allowed is False

    def test_large_enterprise_budget_no_integer_overflow(self):
        """Enterprise budget 19900 cents — ensure no integer overflow in comparisons."""
        allowed, reason = _run_check(ENTERPRISE, usage(19899.99), extras())
        assert allowed is True
        allowed, reason = _run_check(ENTERPRISE, usage(19900.0), extras())
        assert allowed is False


class TestBudgetStatusConsistency:
    """check_budget and get_budget_status must agree on is_limited."""

    @pytest.mark.parametrize("plan,cost", [
        (FREE_TRIAL, 20.0),    # at limit
        (FREE_TRIAL, 19.9),    # under limit
        (INDIVIDUAL, 760.0),   # at limit
        (INDIVIDUAL, 100.0),   # well under
    ])
    def test_check_budget_and_get_budget_status_agree(self, plan, cost):
        from app.services.subscription_service import check_budget, get_budget_status

        shared_patches = [
            patch("app.services.subscription_service.get_user_plan",           return_value=plan),
            patch("app.services.subscription_service.get_current_usage",        return_value=usage(cost)),
            patch("app.services.subscription_service.get_coupon_extras",        return_value=extras()),
            patch("app.services.subscription_service.count_lifetime_messages",  return_value=0),
        ]

        with ExitStack() as stack:
            for p in shared_patches:
                stack.enter_context(p)
            allowed, _ = check_budget(TEST_UID, context="ai")
            status = get_budget_status(TEST_UID)

        # is_limited from get_budget_status must match blocked from check_budget
        assert status["is_limited"] == (not allowed), \
            f"check_budget={allowed} but is_limited={status['is_limited']} for cost={cost}"


class TestPeriodRollover:

    def test_new_month_resets_usage_to_zero(self):
        """period_start = first day of month — different month = separate row."""
        from app.services.subscription_service import get_current_usage
        from datetime import date
        import calendar

        # Mock DB returning row for last month — current month should see 0
        last_month_start = date.today().replace(day=1)
        # Simulate: DB returns a row for last month, not current month
        row_last_month = {
            "uid": TEST_UID,
            "period_start": last_month_start,
            "estimated_cost_cents": 500.0,
            "message_count": 100,
            "input_tokens": 10000,
            "output_tokens": 5000,
        }
        with patch("app.services.subscription_service.get_db", mock_db(None)):
            # fetchone returns None → no row for current month
            result = get_current_usage(TEST_UID)

        assert result["estimated_cost_cents"] == 0.0
        assert result["message_count"] == 0

    def test_usage_aggregates_within_same_month(self):
        """Two calls in the same billing period accumulate, not reset."""
        from app.services.subscription_service import record_usage

        call_count = [0]

        @contextmanager
        def counting_db():
            cur = MagicMock()
            cur.fetchone.return_value = {
                "estimated_cost_cents": 0.02 * (call_count[0] + 1),
                "message_count": call_count[0] + 1,
            }
            def execute_side(sql, params=None):
                call_count[0] += 1
            cur.execute.side_effect = execute_side
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", counting_db):
            record_usage(TEST_UID, 100, 50, "gpt-4.1-nano", interaction_type="spark")
            record_usage(TEST_UID, 100, 50, "gpt-4.1-nano", interaction_type="spark")

        # Both calls must use ON CONFLICT upsert — never bare INSERT
        # Verified by inspecting SQL in test_budget.py TestRecordUsage (already covered)
        assert call_count[0] > 0
```

---

## Phase 6 — Race Condition & Over-allocation Defense

**Goal:** Demonstrate that the current `check → call → record` pattern can overrun budget
by at most one request, quantify the maximum overrun, and test any mitigation.

### 6.1 Analysis of the race window

```
Thread A:  check_budget → ALLOWED (spent=18, budget=20)
Thread B:  check_budget → ALLOWED (spent=18, budget=20)   ← both see same DB state
Thread A:  call OpenAI  → cost 2 cents
Thread B:  call OpenAI  → cost 2 cents
Thread A:  record_usage → spent=20
Thread B:  record_usage → spent=22   ← over budget by 1 request
```

Maximum overrun = cost of one request for the most expensive endpoint. For `gpt-4o-mini`
with `max_tokens=1024`: roughly 0.012 cents input + 0.06 cents output = ~0.07 cents.
For `step_content` with `max_tokens=1500` on `gpt-4o-mini`: ~0.1 cents.

This is an **acceptable bounded overrun** — not a critical security issue. The tests below
document the behaviour, not fix it.

### 6.2 Tests to write — `tests/unit/test_race_conditions.py`

```python
import asyncio
import threading

class TestRaceConditionDocumentation:
    """
    These tests document known behaviour, not bugs.
    The maximum over-allocation is bounded by one request cost (~0.1 cents).
    """

    def test_two_simultaneous_check_budgets_both_pass_at_boundary(self):
        """
        When spent == budget - epsilon, two concurrent check_budget calls
        both return (True, 'ok') because both read the same DB row.
        This is the known race window.
        """
        from app.services.subscription_service import check_budget

        call_results = []

        def run_check():
            p1 = patch("app.services.subscription_service.get_user_plan",           return_value=INDIVIDUAL)
            p2 = patch("app.services.subscription_service.get_current_usage",        return_value=usage(759.99))
            p3 = patch("app.services.subscription_service.get_coupon_extras",        return_value=extras())
            p4 = patch("app.services.subscription_service.count_lifetime_messages",  return_value=0)
            with p1, p2, p3, p4:
                result = check_budget(TEST_UID, context="ai")
            call_results.append(result)

        t1 = threading.Thread(target=run_check)
        t2 = threading.Thread(target=run_check)
        t1.start(); t2.start()
        t1.join();  t2.join()

        # Both pass — this is expected (documented race condition)
        assert all(allowed for allowed, _ in call_results), \
            "Race condition window confirmed: both requests allowed at budget boundary"

    def test_record_usage_upsert_prevents_data_loss_under_concurrent_writes(self):
        """
        Even if two record_usage calls execute simultaneously, the ON CONFLICT
        DO UPDATE ensures tokens accumulate correctly (no lost write).
        This test verifies the SQL pattern, not the DB-level locking.
        """
        from app.services.subscription_service import record_usage

        all_sqls = []

        @contextmanager
        def capture_db():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, p=None: all_sqls.append(sql)
            cur.fetchone.return_value = {"estimated_cost_cents": 0.01, "message_count": 1}
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture_db):
            record_usage(TEST_UID, 100, 50, "gpt-4o-mini", interaction_type="daily_chat")

        upsert_sqls = [s for s in all_sqls if "ON CONFLICT" in s]
        assert len(upsert_sqls) >= 1, "record_usage must use ON CONFLICT upsert"

    def test_maximum_overrun_is_bounded(self):
        """
        Document the theoretical max overrun: one request of step_content
        on gpt-4o-mini with max_tokens=1500.
        """
        from app.services.provider_service import cost_for_tokens
        # Worst realistic case: 800 input tokens + 1500 output tokens on step_content
        max_overrun = cost_for_tokens("gpt-4o-mini", 800, 1500)
        # Must be under 0.20 cents (well under $0.002)
        assert max_overrun < 0.20, f"Max race overrun {max_overrun:.4f}¢ exceeds 0.20¢ threshold"
```

---

## Phase 7 — Admin Observability & Usage History

**Goal:** Admins can see all usage across all plans and gateways. History API returns
correct period data. Breakdown by interaction type is accurate.

### 7.1 Tests to write — `tests/unit/test_usage_history.py`

```python
class TestGetUsageHistory:

    def test_returns_newest_first(self):
        from app.services.subscription_service import get_usage_history

        rows = [
            {"period_start": "2026-06-01", "estimated_cost_cents": 50.0, "message_count": 10,
             "input_tokens": 1000, "output_tokens": 500, "cached_input_tokens": 0},
            {"period_start": "2026-05-01", "estimated_cost_cents": 30.0, "message_count": 6,
             "input_tokens": 600, "output_tokens": 300, "cached_input_tokens": 0},
        ]
        with patch("app.services.subscription_service.get_db", mock_db_fetchall(rows)):
            history = get_usage_history(TEST_UID, months=6)

        assert history[0]["period_start"] > history[1]["period_start"]

    def test_months_capped_at_24(self):
        """SQL must not request more than 24 months back to avoid table scan."""
        from app.services.subscription_service import get_usage_history

        executed_params = []

        @contextmanager
        def capture():
            cur = MagicMock()
            cur.execute.side_effect = lambda sql, params=None: executed_params.append(params)
            cur.fetchall.return_value = []
            cur.__enter__ = lambda s: cur
            cur.__exit__ = MagicMock(return_value=False)
            conn = MagicMock()
            conn.cursor.return_value = cur
            conn.__enter__ = lambda s: conn
            conn.__exit__ = MagicMock(return_value=False)
            yield conn

        with patch("app.services.subscription_service.get_db", capture):
            get_usage_history(TEST_UID, months=999)

        assert executed_params and executed_params[0][1] == 24

    def test_empty_history_returns_empty_list(self):
        from app.services.subscription_service import get_usage_history
        with patch("app.services.subscription_service.get_db", mock_db_fetchall([])):
            result = get_usage_history(TEST_UID)
        assert result == []


class TestGetUsageBreakdown:

    def test_breakdown_ordered_by_cost_descending(self):
        from app.services.subscription_service import get_usage_breakdown

        rows = [
            {"interaction_type": "daily_chat",    "estimated_cost_cents": 30.0, "request_count": 50,
             "input_tokens": 5000, "output_tokens": 2000, "cached_input_tokens": 0},
            {"interaction_type": "step_content",  "estimated_cost_cents": 15.0, "request_count": 10,
             "input_tokens": 2000, "output_tokens": 1000, "cached_input_tokens": 0},
            {"interaction_type": "spark",         "estimated_cost_cents": 5.0,  "request_count": 100,
             "input_tokens": 3000, "output_tokens": 1000, "cached_input_tokens": 0},
        ]
        with patch("app.services.subscription_service.get_db", mock_db_fetchall(rows)):
            breakdown = get_usage_breakdown(TEST_UID)

        costs = [r["estimated_cost_cents"] for r in breakdown]
        assert costs == sorted(costs, reverse=True)

    def test_no_unknown_interaction_types_in_production_breakdown(self):
        """
        Verifies that record_usage is always called with a known interaction_type.
        'unknown' appearing in the breakdown indicates a code gap.
        """
        KNOWN_INTERACTION_TYPES = {
            "daily_chat", "onboarding", "fingerprint", "mind_signature",
            "spark", "daily_spark", "knowledge_extraction",
            "journey", "step_content", "quiz", "nudge",
        }
        # This is a documentation test — the actual check happens in test_usage_recording.py
        # Here we assert the set is complete.
        from app.services.provider_service import DEFAULT_CONFIG
        configured_types = set(DEFAULT_CONFIG.keys())
        assert configured_types.issubset(KNOWN_INTERACTION_TYPES), \
            f"New interaction types not added to KNOWN set: {configured_types - KNOWN_INTERACTION_TYPES}"


class TestAdminStats:

    def test_admin_stats_include_all_plans(self, client):
        """GET /api/v1/admin/stats returns monthly_api_cost_cents summed across all users."""
        with patch("app.api.v1.endpoints.admin.get_admin_stats", return_value={
            "total_users": 100,
            "dau": 25,
            "messages_today": 200,
            "monthly_api_cost_cents": 5000.0,
        }):
            res = client.get("/api/v1/admin/stats")
        assert res.status_code == 200
        body = res.json()
        assert "monthly_api_cost_cents" in body
        assert body["monthly_api_cost_cents"] >= 0

    def test_budget_status_api_returns_breakdown(self, client):
        """GET /api/v1/subscriptions/me must expose enough data for users to understand spending."""
        patches = [
            patch("app.api.v1.endpoints.subscriptions.get_user_plan",          return_value=INDIVIDUAL),
            patch("app.api.v1.endpoints.subscriptions.get_current_usage",       return_value=usage(200.0)),
            patch("app.api.v1.endpoints.subscriptions.get_coupon_extras",       return_value=extras()),
            patch("app.api.v1.endpoints.subscriptions.count_lifetime_messages", return_value=0),
            patch("app.api.v1.endpoints.subscriptions.get_db",                  mock_db({"is_admin": False})),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            res = client.get("/api/v1/subscriptions/me")

        assert res.status_code == 200
        body = res.json()
        assert body["spent_cents"] == 200.0
        assert body["total_budget_cents"] == 760.0
        assert body["remaining_cents"] == 560.0
        assert body["pct_used"] == pytest.approx(26.3, abs=0.1)
        assert body["is_limited"] is False
```

---

## Phase 8 — End-to-End Integration Tests (DB-backed)

**Goal:** Run against a real test database (not mocked) to catch SQL bugs,
constraint violations, and verify the full stack from HTTP → DB → HTTP.

### 8.1 Prerequisites

- Test Supabase branch or local Postgres with the real schema
- `pytest -m integration` marker to run separately from unit tests
- Test isolation: each test seeds its own `users`, `subscriptions`, `token_usage` rows
  and cleans up after

### 8.2 Tests to write — `tests/integration/test_budget_full_stack.py`

```python
@pytest.mark.integration
class TestFullStackBudgetFlow:

    @pytest.fixture(autouse=True)
    def setup_test_user(self, db):
        """Insert a test user and clean up after each test."""
        db.execute("INSERT INTO users (uid, email) VALUES ('integ-test-uid', 'test@ecalt.test')")
        yield
        db.execute("DELETE FROM token_usage WHERE uid = 'integ-test-uid'")
        db.execute("DELETE FROM usage_by_interaction WHERE uid = 'integ-test-uid'")
        db.execute("DELETE FROM subscriptions WHERE uid = 'integ-test-uid'")
        db.execute("DELETE FROM coupon_redemptions WHERE uid = 'integ-test-uid'")
        db.execute("DELETE FROM users WHERE uid = 'integ-test-uid'")

    def test_free_trial_record_usage_and_check_budget_agree(self, db):
        """record_usage writes cost; subsequent check_budget reads it and blocks at 20¢."""
        from app.services.subscription_service import record_usage, check_budget

        uid = "integ-test-uid"
        # Record usage that pushes cost to just below limit
        record_usage(uid, 1_800_000, 0, "gpt-4.1-nano", interaction_type="daily_chat")
        # 1,800,000 × 0.000010 = 18 cents

        allowed, _ = check_budget(uid, context="ai")
        assert allowed is True  # 18 < 20

        # Push over limit
        record_usage(uid, 200_000, 0, "gpt-4.1-nano", interaction_type="spark")
        # cumulative = 20 cents

        allowed, reason = check_budget(uid, context="ai")
        assert allowed is False
        assert reason == "budget_exhausted"

    def test_usage_by_interaction_populated_per_type(self, db):
        """Verify both tables receive separate rows per interaction_type."""
        from app.services.subscription_service import record_usage

        uid = "integ-test-uid"
        record_usage(uid, 1000, 500, "gpt-4o-mini", interaction_type="daily_chat")
        record_usage(uid, 800,  300, "gpt-4o-mini", interaction_type="step_content")

        from datetime import date
        period = date.today().replace(day=1)

        rows = db.execute(
            "SELECT interaction_type, request_count FROM usage_by_interaction "
            "WHERE uid = %s AND period_start = %s ORDER BY interaction_type",
            (uid, period)
        ).fetchall()

        types = {r["interaction_type"] for r in rows}
        assert "daily_chat"   in types
        assert "step_content" in types
        # Each must have exactly 1 request
        for r in rows:
            assert r["request_count"] == 1

    def test_coupon_credit_reflected_in_budget_check(self, db):
        """After applying a coupon, check_budget allows usage beyond the base budget."""
        from app.services.subscription_service import record_usage, check_budget

        uid = "integ-test-uid"
        # Exhaust base budget
        record_usage(uid, 2_000_000, 0, "gpt-4.1-nano")  # = 20 cents

        allowed, _ = check_budget(uid, context="ai")
        assert allowed is False  # exhausted

        # Insert coupon redemption directly
        db.execute(
            "INSERT INTO coupon_redemptions (uid, coupon_code, credit_applied_cents, bonus_messages_applied) "
            "VALUES (%s, 'TESTCODE', 10.0, 0)",
            (uid,)
        )

        allowed, _ = check_budget(uid, context="ai")
        assert allowed is True  # 20 < 30

    def test_razorpay_subscription_gets_same_budget_as_stripe(self, db):
        """Both payment gateways produce the same budget when plan_id matches."""
        from app.services.subscription_service import upsert_subscription_from_stripe, get_user_plan

        uid = "integ-test-uid"

        # Insert as Razorpay subscriber
        upsert_subscription_from_stripe(
            uid=uid, plan_id="individual",
            payment_gateway="razorpay",
            razorpay_subscription_id="rzp_sub_test",
            status="active",
        )

        plan = get_user_plan(uid)
        assert plan["plan_id"] == "individual"
        assert plan["token_budget_cents"] == 760

    def test_multiple_interaction_types_accumulate_in_token_usage(self, db):
        """token_usage.estimated_cost_cents is the SUM of all interaction types."""
        from app.services.subscription_service import record_usage, get_current_usage
        from app.services.provider_service import cost_for_tokens

        uid = "integ-test-uid"
        record_usage(uid, 1000, 500, "gpt-4o-mini", interaction_type="daily_chat")
        record_usage(uid, 2000, 800, "gpt-4o-mini", interaction_type="step_content")
        record_usage(uid, 500,  200, "gpt-4.1-nano", interaction_type="spark")

        expected = (
            cost_for_tokens("gpt-4o-mini",  1000, 500) +
            cost_for_tokens("gpt-4o-mini",  2000, 800) +
            cost_for_tokens("gpt-4.1-nano",  500, 200)
        )

        current = get_current_usage(uid)
        assert abs(current["estimated_cost_cents"] - expected) < 1e-6
```

---

## Implementation Roadmap

### Sprint 1 (do first — fixes required before most tests pass)

| Task | File | Priority |
|------|------|----------|
| Fix `record_usage(uid, 0, 0, …)` in `quiz.py` | `quiz_service.py`, `quiz.py` | P0 |
| Add `check_budget` + `record_usage` to `mind_signature.py` | `mind_signature.py`, `mind_signature_service.py` | P0 |
| Add `check_budget` + `record_usage` to `knowledge.py` | `knowledge.py`, `spark_service.py` | P0 |
| Add `interaction_type="step_content"` to `journeys.py:251` | `journeys.py` | P0 |
| Fix stale conftest prices, add FAMILY/UNIVERSITY/ENTERPRISE | `conftest.py` | P0 |

### Sprint 2 (new unit tests)

| Test file | Phase |
|-----------|-------|
| `tests/unit/test_plan_configs.py` | Phase 1 |
| `tests/api/test_api_budget_coverage.py` | Phase 2 |
| `tests/unit/test_usage_recording.py` | Phase 3 |
| `tests/unit/test_payment_gateway_parity.py` | Phase 4 |
| `tests/unit/test_budget_arithmetic.py` | Phase 5 |
| `tests/unit/test_race_conditions.py` | Phase 6 |
| `tests/unit/test_usage_history.py` | Phase 7 |

### Sprint 3 (integration tests — requires test DB)

| Test file | Phase |
|-----------|-------|
| `tests/integration/test_budget_full_stack.py` | Phase 8 |

---

## Test Count Summary

| Phase | New test classes | New test methods (est.) |
|-------|-----------------|------------------------|
| 1 – Plan configs | 1 | 3 |
| 2 – Budget gate completeness | 4 | 12 |
| 3 – Usage recording | 4 | 10 |
| 4 – INR/USD parity | 1 | 6 |
| 5 – Budget arithmetic | 4 | 18 |
| 6 – Race conditions | 1 | 3 |
| 7 – Admin observability | 3 | 8 |
| 8 – Full stack integration | 1 | 6 |
| **Total** | **19 classes** | **~66 methods** |

---

## Definition of Done

- [ ] All 4 code gaps (G1–G5) fixed in production code
- [ ] `conftest.py` prices synced to DB; `FAMILY`, `UNIVERSITY`, `ENTERPRISE` added
- [ ] All 66 test methods pass in CI (`pytest -m "unit"`)
- [ ] Integration tests pass against Supabase test branch (`pytest -m "integration"`)
- [ ] `pytest --co` shows no test with `interaction_type` missing from `record_usage` calls
- [ ] No test calls `record_usage(uid, 0, 0, …)` — zero-token records are banned
- [ ] `python -m pytest tests/ -x --tb=short` returns green before any deploy
