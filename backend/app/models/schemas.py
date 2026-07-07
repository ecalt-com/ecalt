from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone
import uuid


AgeGroup = Literal["kids", "teens", "adults", "all"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
StepType = Literal["concept", "practice", "challenge", "explore"]


class JourneyStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique step identifier")
    title: str = Field(..., description="Short display title for the step")
    description: str = Field(..., description="What the learner will do or discover in this step")
    type: StepType = Field(..., description="Step category: concept | practice | challenge | explore")
    estimated_minutes: int = Field(..., description="Estimated time to complete the step, in minutes", gt=0)
    completed: bool = Field(False, description="Whether the learner has completed this step")
    content: Optional[str] = Field(None, description="Full step content / lesson body (populated on demand)")
    core_question: Optional[str] = Field(None, description="The one question this step answers (seeds content generation)")
    seed_facts: Optional[List[str]] = Field(None, description="Specific facts/examples the step content is built around")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "dna-1",
                "title": "What is DNA?",
                "description": "Discover the molecule that holds the blueprint for all life on Earth",
                "type": "concept",
                "estimated_minutes": 15,
                "completed": False,
                "content": None,
            }
        }
    }


class Journey(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique journey identifier")
    question: str = Field(..., description="The original curiosity question that spawned this journey")
    title: str = Field(..., description="Human-readable journey title")
    description: str = Field(..., description="One-sentence summary of what the learner will understand")
    age_group: AgeGroup = Field("all", description="Target audience: kids | teens | adults | all")
    difficulty: Difficulty = Field("beginner", description="Difficulty level: beginner | intermediate | advanced")
    estimated_hours: float = Field(..., description="Total estimated time to complete all steps, in hours", gt=0)
    steps: List[JourneyStep] = Field(..., description="Ordered list of learning steps")
    tags: List[str] = Field(..., description="Topic tags for filtering and discovery")
    icon: str = Field(..., description="Emoji icon representing the journey topic")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of when the journey was created",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "journey-dna",
                "question": "How does DNA work?",
                "title": "The Code of Life: DNA Decoded",
                "description": "From double helix to protein factories — unlock the molecular language that makes you, you.",
                "age_group": "all",
                "difficulty": "beginner",
                "estimated_hours": 3.0,
                "icon": "🧬",
                "tags": ["biology", "genetics", "molecules"],
                "steps": [],
                "created_at": "2026-05-16T00:00:00+00:00",
            }
        }
    }


class MissionStep(BaseModel):
    title: str
    type: StepType
    minutes: int = Field(..., gt=0)


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    tagline: str
    category: str
    difficulty: Difficulty
    estimated_minutes: int
    icon: str
    steps: List[MissionStep]


class SparkRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=300, description="Curiosity question (max 300 chars)")
    session_id: Optional[str] = Field(None, max_length=128, description="Client session UUID — used for guest rate limiting; ignored when auth token present")


class SparkResponse(BaseModel):
    answer: str = Field(..., description="Short vivid answer to the question (2-3 sentences)")
    mission: Mission = Field(..., description="Proposed learning mission")
    sparks_used: int
    sparks_remaining: int


class ExploreRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Free-form curiosity question (1–500 chars)")
    age_group: Optional[AgeGroup] = Field("all", description="Tailor content for a specific age group")
    level: Optional[str] = Field(None, description="Preferred difficulty hint (optional)")
    learner_purpose: Optional[str] = Field(None, description="Why the user is exploring: research_paper | professional_growth | personal_curiosity | teaching_others | fun")
    topic_expertise: Optional[str] = Field(None, description="Self-reported expertise on this specific topic: beginner | intermediate | advanced | expert")
    refinement_context: Optional[str] = Field(None, max_length=600, description="Feedback on a rejected journey preview — triggers targeted regeneration")

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "How does DNA work?",
                "age_group": "all",
                "level": None,
                "learner_purpose": "personal_curiosity",
                "topic_expertise": "beginner",
            }
        }
    }


class ExploreResponse(BaseModel):
    journey: Journey = Field(..., description="The AI-generated Journey for the submitted question")


class JourneyWithProgress(Journey):
    steps_done: int = Field(0, description="Number of steps the user has completed")
    last_active_at: Optional[str] = Field(None, description="ISO timestamp of most recent step completion")


class JourneysResponse(BaseModel):
    journeys: List[Journey] = Field(..., description="List of Journey objects")
    in_progress: List[JourneyWithProgress] = Field(default_factory=list, description="Journeys the user has started but not finished")
    total: int = Field(..., description="Total number of journeys returned")


class StepContentResponse(BaseModel):
    journey_id: str
    step_id: str
    content: str
    cached: bool = False


class SessionStatus(BaseModel):
    session_id: str
    sparks_used: int = Field(..., ge=0)
    sparks_remaining: int = Field(..., ge=0)
    limit: int = Field(5, description="Total free sparks per session window")
