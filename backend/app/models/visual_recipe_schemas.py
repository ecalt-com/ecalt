"""Visual Intelligence Layer — Phase 2: typed recipe schemas for the first
10 native visual patterns (spec section 10-12).

These are pure data contracts: "generate instructions, not pixels" (spec
section 1). No renderer lives here — rendering is frontend work, documented
in plans/visual-intelligence/frontend-changes.md rather than implemented
directly, per standing project convention. A recipe is only ever allowed to
become part of a VLO after it validates against its pattern's schema here.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional

# ── shared building blocks ──────────────────────────────────────────────────


class Connection(BaseModel):
    from_: str = Field(..., alias="from")
    to: str

    model_config = {"populate_by_name": True}


# ── the 10 patterns ─────────────────────────────────────────────────────────


class ProcessFlowNode(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    role: Literal["input", "process", "output"]


class ProcessFlowRecipe(BaseModel):
    pattern: Literal["process_flow"] = "process_flow"
    title: str
    nodes: List[ProcessFlowNode] = Field(..., min_length=2, max_length=12)
    connections: List[Connection]
    progressiveReveal: bool = True


class CycleNode(BaseModel):
    id: str
    label: str = Field(..., max_length=60)


class CycleRecipe(BaseModel):
    pattern: Literal["cycle"] = "cycle"
    title: str
    nodes: List[CycleNode] = Field(..., min_length=3, max_length=8)
    connections: List[Connection]
    progressiveReveal: bool = True
    looping: bool = True


class CauseEffectNode(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    role: Literal["cause", "mechanism", "effect"]


class CauseEffectRecipe(BaseModel):
    pattern: Literal["cause_effect"] = "cause_effect"
    title: str
    nodes: List[CauseEffectNode] = Field(..., min_length=2, max_length=6)
    connections: List[Connection]


class ComparisonColumn(BaseModel):
    id: str
    label: str = Field(..., max_length=40)
    items: List[str] = Field(..., min_length=1, max_length=8)


class ComparisonRecipe(BaseModel):
    pattern: Literal["comparison"] = "comparison"
    title: str
    # Two-column default; three-way is the spec's only named extension.
    columns: List[ComparisonColumn] = Field(..., min_length=2, max_length=3)


class TimelineEvent(BaseModel):
    id: str
    label: str = Field(..., max_length=80)
    when: str  # absolute date or relative-order label ("1789", "Step 1")


class TimelineRecipe(BaseModel):
    pattern: Literal["timeline"] = "timeline"
    title: str
    events: List[TimelineEvent] = Field(..., min_length=2, max_length=12)
    progressiveReveal: bool = True


class HierarchyNode(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    parentId: Optional[str] = None


class HierarchyRecipe(BaseModel):
    pattern: Literal["hierarchy"] = "hierarchy"
    title: str
    nodes: List[HierarchyNode] = Field(..., min_length=2, max_length=20)

    @field_validator("nodes")
    @classmethod
    def _max_depth(cls, nodes: List[HierarchyNode]) -> List[HierarchyNode]:
        by_id = {n.id: n for n in nodes}

        def depth(node: HierarchyNode, seen: frozenset) -> int:
            if node.parentId is None or node.parentId not in by_id or node.id in seen:
                return 1
            return 1 + depth(by_id[node.parentId], seen | {node.id})

        for n in nodes:
            if depth(n, frozenset()) > 4:
                raise ValueError(f"hierarchy node {n.id!r} exceeds the max depth guardrail (4)")
        return nodes


class Part(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    description: Optional[str] = Field(None, max_length=200)


class PartToWholeRecipe(BaseModel):
    pattern: Literal["part_to_whole"] = "part_to_whole"
    title: str
    whole: str
    parts: List[Part] = Field(..., min_length=2, max_length=12)


class BeforeAfterState(BaseModel):
    label: str = Field(..., max_length=60)
    description: str = Field(..., max_length=300)


class BeforeAfterRecipe(BaseModel):
    pattern: Literal["before_after"] = "before_after"
    title: str
    before: BeforeAfterState
    after: BeforeAfterState


class QuantityItem(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    value: float
    unit: Optional[str] = None


class QuantityComparisonRecipe(BaseModel):
    pattern: Literal["quantity_comparison"] = "quantity_comparison"
    title: str
    items: List[QuantityItem] = Field(..., min_length=2, max_length=8)

    @field_validator("items")
    @classmethod
    def _no_negative_values(cls, items: List[QuantityItem]) -> List[QuantityItem]:
        # Negative magnitudes can't be represented as bar/area scale without
        # misleading the learner (spec section 11.9).
        if any(i.value < 0 for i in items):
            raise ValueError("quantity_comparison values must be non-negative")
        return items


class SequenceStep(BaseModel):
    id: str
    label: str = Field(..., max_length=60)
    content: str = Field(..., max_length=300)


class ProgressiveSequenceRecipe(BaseModel):
    pattern: Literal["progressive_sequence"] = "progressive_sequence"
    title: str
    steps: List[SequenceStep] = Field(..., min_length=2, max_length=8)
    autoPlay: bool = False


PATTERN_SCHEMAS: dict[str, type[BaseModel]] = {
    "process_flow": ProcessFlowRecipe,
    "cycle": CycleRecipe,
    "cause_effect": CauseEffectRecipe,
    "comparison": ComparisonRecipe,
    "timeline": TimelineRecipe,
    "hierarchy": HierarchyRecipe,
    "part_to_whole": PartToWholeRecipe,
    "before_after": BeforeAfterRecipe,
    "quantity_comparison": QuantityComparisonRecipe,
    "progressive_sequence": ProgressiveSequenceRecipe,
}


def validate_recipe(pattern: str, recipe: dict) -> BaseModel:
    """Raises KeyError for an unknown pattern, pydantic.ValidationError for
    a recipe that doesn't match its pattern's schema. Callers decide what to
    do on failure (visual_recipe_service downgrades to TEXT_ONLY)."""
    schema = PATTERN_SCHEMAS[pattern]
    return schema(**recipe)
