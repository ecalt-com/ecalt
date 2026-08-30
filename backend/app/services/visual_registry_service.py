"""Visual Intelligence Layer — Phase 1: VLO/plan persistence and cache keys.

Hashing follows the scheme in backend/plans/visual-intelligence/README.md /
spec section 15 (visual-plan / VLO cache keys), truncated to 16 hex chars —
plenty of collision resistance for a cache key, and short enough to stay
readable in a unique index.
"""
import hashlib
import json

from app.core.database import get_db
from app.models.visual_schemas import VisualPlan


def hash_text(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()[:16]


def concept_hash(concept_key: str) -> str:
    return hash_text(concept_key)


def objective_hash(learning_objective: str) -> str:
    return hash_text(learning_objective)


def find_reusable_vlo(
    concept_key: str, learning_objective: str, grade_band: str, modality: str, min_version: int = 1,
) -> dict | None:
    """Exact-match VLO lookup (spec section 16, step 2: exact VLO match -> reuse).

    Compatible-but-not-exact matching (step 3) is deferred — v1 only reuses
    when concept + objective + grade band + modality all line up.

    min_version implements spec section 15's versioning principle: bumping a
    renderer/recipe-prompt version (visual_recipe_service.RECIPE_PROMPT_VERSION)
    makes VLOs built under older versions invisible to reuse without deleting
    them — the next plan for that step creates a fresh, higher-version VLO
    instead (lazy regeneration, same pattern as ai_service.CONTENT_PROMPT_VERSION).
    """
    if modality == "none":
        return None
    obj_hash = objective_hash(learning_objective)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, concept_key, learning_objective_hash, grade_band, modality,
                       pedagogical_role, renderer_type, recipe, content_hash, version,
                       status, effectiveness_score, reuse_count
                FROM visual_learning_objects
                WHERE concept_key = %s
                  AND learning_objective_hash = %s
                  AND grade_band = %s
                  AND modality = %s
                  AND status = 'active'
                  AND version >= %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (concept_key, obj_hash, grade_band, modality, min_version),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_active_vlo(
    concept_key: str,
    learning_objective: str,
    grade_band: str,
    modality: str,
    pedagogical_role: str,
    renderer_type: str,
    recipe: dict,
    version: int = 1,
) -> str:
    """Insert a freshly-rendered VLO as immediately active — v1 has no async
    render/validate step (the recipe is already schema-validated by the
    caller), so there's nothing left to wait on. The identity unique index
    (which includes `version`) makes this idempotent: a concurrent request
    for the same concept+objective+grade+modality+recipe+version reuses the
    same row instead of racing to create duplicates."""
    obj_hash = objective_hash(learning_objective)
    c_hash = hash_text(json.dumps(recipe, sort_keys=True))
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO visual_learning_objects
                    (concept_key, learning_objective_hash, grade_band, modality,
                     pedagogical_role, renderer_type, recipe, content_hash, version, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, 'active')
                ON CONFLICT (concept_key, learning_objective_hash, grade_band, modality, content_hash, version)
                DO UPDATE SET updated_at = now()
                RETURNING id
                """,
                (
                    concept_key, obj_hash, grade_band, modality, pedagogical_role,
                    renderer_type, json.dumps(recipe), c_hash, version,
                ),
            )
            return cur.fetchone()["id"]


def record_vlo_reuse(vlo_id: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visual_learning_objects SET reuse_count = reuse_count + 1, updated_at = now() WHERE id = %s",
                (vlo_id,),
            )


def create_visual_asset(
    vlo_id: str,
    asset_type: str,
    status: str = "active",
    storage_key: str | None = None,
    external_url: str | None = None,
    source_type: str | None = None,
    source_name: str | None = None,
    license_type: str | None = None,
    license_url: str | None = None,
    attribution: str | None = None,
    commercial_use_allowed: bool | None = None,
    modification_allowed: bool | None = None,
    width: int | None = None,
    height: int | None = None,
    file_size_bytes: int | None = None,
) -> str:
    """Attach a retrieved or generated asset to a VLO (spec section 6.2,
    shared by Phase 5 retrieval and Phase 6 generation)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO visual_assets
                    (vlo_id, asset_type, storage_key, external_url, source_type, source_name,
                     license_type, license_url, attribution, commercial_use_allowed,
                     modification_allowed, width, height, file_size_bytes, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    vlo_id, asset_type, storage_key, external_url, source_type, source_name,
                    license_type, license_url, attribution, commercial_use_allowed,
                    modification_allowed, width, height, file_size_bytes, status,
                ),
            )
            return cur.fetchone()["id"]


def set_effectiveness_score(vlo_id: str, score: float) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visual_learning_objects SET effectiveness_score = %s, updated_at = now() WHERE id = %s",
                (score, vlo_id),
            )


def get_step_visual(journey_id: str, step_id: str) -> dict | None:
    """Read-only join of visual_plans -> visual_learning_objects -> (most
    recent active) visual_assets for the API layer (spec section 13). None
    means no plan exists yet for this step — the caller (endpoint)
    distinguishes that from "planned but no visual needed" using the row's
    own selected_strategy/execution_status.

    renderer_type is set for native-render VLOs (recipe holds the typed
    data); asset_url is set instead for retrieved/generated-image VLOs
    (renderer_type/recipe are empty for those) -- see
    visual_orchestrator_service._try_retrieval / _try_image_generation.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.selected_strategy, p.execution_status,
                       v.id AS vlo_id, v.modality, v.renderer_type, v.recipe, v.pedagogical_role,
                       a.external_url AS asset_url, a.asset_type AS asset_type,
                       a.attribution AS asset_attribution, a.license_type AS asset_license_type,
                       a.source_name AS asset_source_name
                FROM visual_plans p
                LEFT JOIN visual_learning_objects v ON v.id = p.vlo_id
                LEFT JOIN LATERAL (
                    SELECT external_url, asset_type, attribution, license_type, source_name
                    FROM visual_assets
                    WHERE vlo_id = v.id AND status = 'active'
                    ORDER BY created_at DESC
                    LIMIT 1
                ) a ON true
                WHERE p.journey_id = %s AND p.step_id = %s
                """,
                (journey_id, step_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def upsert_visual_plan(
    journey_id: str,
    step_id: str,
    concept_key: str,
    plan: VisualPlan,
    planner_model: str,
    selected_strategy: str,
    execution_status: str,
    vlo_id: str | None,
    planner_prompt_version: int,
) -> str:
    """Persist the planning decision so 'why did ECALT choose this visual?'
    is always answerable (spec section 6.3). One row per (journey_id, step_id)
    — re-planning a step upserts in place rather than accumulating history."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO visual_plans
                    (journey_id, step_id, concept_key, plan, planner_model,
                     planner_prompt_version, selected_strategy, execution_status, vlo_id)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                ON CONFLICT (journey_id, step_id) DO UPDATE SET
                    concept_key             = EXCLUDED.concept_key,
                    plan                    = EXCLUDED.plan,
                    planner_model           = EXCLUDED.planner_model,
                    planner_prompt_version  = EXCLUDED.planner_prompt_version,
                    selected_strategy       = EXCLUDED.selected_strategy,
                    execution_status        = EXCLUDED.execution_status,
                    vlo_id                  = EXCLUDED.vlo_id,
                    updated_at              = now()
                RETURNING id
                """,
                (
                    journey_id, step_id, concept_key, plan.model_dump_json(), planner_model,
                    planner_prompt_version, selected_strategy, execution_status, vlo_id,
                ),
            )
            return cur.fetchone()["id"]
