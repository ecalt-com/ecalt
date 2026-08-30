"""Domain contracts for the ECALT Visual Intelligence Layer.

The planner LLM produces a VisualPlan; the deterministic router turns it into
a VisualStrategy. Renderers (Phase 2), retrieval (Phase 5), generation
(Phase 6), and telemetry (Phase 4, VisualEvent below) all build on these.
"""
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from typing import List, Literal, Optional

PedagogicalRole = Literal[
    "hook", "anchor", "explain", "compare", "demonstrate", "simulate", "practice", "recap",
]

VisualModality = Literal[
    "none",
    "native_diagram",
    "progressive_reveal",
    "animated_process",
    "interactive",
    "simulation",
    "retrieved_image",
    "retrieved_video",
    "generated_image",
    "generated_video",
]

# Deterministic router output. NATIVE_INTERACTIVE/NATIVE_ANIMATION are folded
# into NATIVE_RENDER for v1 since no renderer registry exists yet (Phase 2).
VisualStrategy = Literal[
    "NONE",
    "REUSE_VLO",
    "NATIVE_RENDER",
    "RETRIEVE_LICENSED_ASSET",
    "GENERATE_IMAGE",
    "GENERATE_VIDEO",
    "TEXT_ONLY",
]

VISUAL_PATTERNS = (
    "process_flow", "cycle", "cause_effect", "comparison", "timeline",
    "hierarchy", "part_to_whole", "before_after", "quantity_comparison",
    "progressive_sequence",
)


class ConceptProperties(BaseModel):
    requiresMotion: bool = False
    requiresSpatialUnderstanding: bool = False
    requiresRealWorldContext: bool = False
    benefitsFromInteraction: bool = False
    requiresQuantitativeManipulation: bool = False


class VisualConcept(BaseModel):
    canonicalName: str
    conceptKey: str


class VisualPlan(BaseModel):
    version: Literal["1.0"] = "1.0"
    visualRequired: bool
    priority: Literal["low", "medium", "high"] = "low"

    concept: VisualConcept
    learningObjective: str
    pedagogicalRole: PedagogicalRole

    conceptProperties: ConceptProperties = Field(default_factory=ConceptProperties)

    recommendedModality: VisualModality = "none"
    fallbackModalities: List[VisualModality] = Field(default_factory=list)

    visualPattern: Optional[str] = None
    visualDescription: str = ""

    generationAllowed: bool = False
    estimatedPedagogicalValue: float = Field(0, ge=0, le=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "version": "1.0",
                "visualRequired": True,
                "priority": "high",
                "concept": {"canonicalName": "Photosynthesis", "conceptKey": "photosynthesis"},
                "learningObjective": "Understand the conversion of light energy into chemical energy",
                "pedagogicalRole": "explain",
                "conceptProperties": {
                    "requiresMotion": True,
                    "requiresSpatialUnderstanding": False,
                    "requiresRealWorldContext": False,
                    "benefitsFromInteraction": False,
                    "requiresQuantitativeManipulation": False,
                },
                "recommendedModality": "animated_process",
                "fallbackModalities": ["native_diagram"],
                "visualPattern": "process_flow",
                "visualDescription": "Sunlight entering a leaf and being converted into glucose",
                "generationAllowed": False,
                "estimatedPedagogicalValue": 0.8,
            }
        }
    }


class StepVisualResponse(BaseModel):
    """Read-only view of the planned visual for one journey step (spec §13's
    GET /api/v1/visual/:vloId, adapted to ECALT's step-scoped granularity —
    see backend/plans/visual-intelligence/README.md §1)."""
    journey_id: str
    step_id: str
    status: Literal["none", "ready", "pending", "unavailable"]
    strategy: Optional[VisualStrategy] = None
    vlo_id: Optional[str] = None  # needed by the frontend to attribute telemetry events
    modality: Optional[VisualModality] = None
    renderer_type: Optional[str] = None
    recipe: Optional[dict] = None
    pedagogical_role: Optional[PedagogicalRole] = None
    # Set instead of renderer_type/recipe for retrieved/generated-image VLOs
    # (modality "retrieved_image" | "generated_image") -- see
    # visual_orchestrator_service._try_retrieval / _try_image_generation.
    asset_url: Optional[str] = None
    asset_type: Optional[str] = None
    attribution: Optional[str] = None
    license_type: Optional[str] = None


VisualEventType = Literal[
    "visual_impression", "visual_started", "visual_completed",
    "visual_replayed", "visual_skipped", "visual_interaction", "visual_error",
]


class VisualEvent(BaseModel):
    """Frontend telemetry payload (spec §22). userId is optional — sparks and
    other unauthenticated surfaces may emit these without a logged-in user.
    eventData is caller-controlled free-form data; keep it to interaction
    shape (e.g. {"action": "slider_change", "from": 10, "to": 25}), never
    learner-identifying content (spec §22)."""
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    eventType: VisualEventType
    userId: Optional[str] = None
    courseId: str
    lessonId: str
    vloId: str
    sessionId: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    eventData: dict = Field(default_factory=dict)


class VisualEventRequest(BaseModel):
    """POST body for the telemetry endpoint — journey_id/step_id/userId come
    from the URL path and auth context, not the client, so they can't be
    spoofed to attribute events to someone else's journey/user."""
    eventType: VisualEventType
    vloId: str
    sessionId: str
    eventData: dict = Field(default_factory=dict)


def visual_plan_text_only(concept_key: str, learning_objective: str) -> VisualPlan:
    """The graceful-degradation plan used when the planner call fails or is
    disabled — never blocks journey generation (spec section 27)."""
    return VisualPlan(
        visualRequired=False,
        concept=VisualConcept(canonicalName=concept_key, conceptKey=concept_key),
        learningObjective=learning_objective,
        pedagogicalRole="explain",
        visualDescription="",
    )
