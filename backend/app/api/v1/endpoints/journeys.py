import json
import logging
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from typing import Optional
from app.models.schemas import Journey, JourneyStep, JourneysResponse, StepContentResponse
from app.core.auth import get_optional_user, get_required_user
from app.core.database import get_db
from app.services.ai_service import generate_step_content
from app.services.subscription_service import check_budget, record_usage
from app.services.provider_service import get_config
from app.services.suggestion_service import generate_next_level, pick_suggestions

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Curated journeys ──────────────────────────────────────────────────────────

SAMPLE_JOURNEYS: list[Journey] = [
    Journey(
        id="journey-dna",
        question="How does DNA work?",
        title="The Code of Life: DNA Decoded",
        description="From double helix to protein factories — unlock the molecular language that makes you, you.",
        age_group="all", difficulty="beginner", estimated_hours=3.0, icon="🧬",
        tags=["biology", "genetics", "molecules"],
        steps=[
            JourneyStep(id="dna-1", title="What is DNA?", description="Discover the molecule that holds the blueprint for all life on Earth", type="concept", estimated_minutes=15),
            JourneyStep(id="dna-2", title="The Double Helix", description="Explore the elegant twisted-ladder structure Watson and Crick revealed", type="concept", estimated_minutes=20),
            JourneyStep(id="dna-3", title="The Four Bases: A, T, G, C", description="Meet the alphabet of life — four chemical letters that write every living thing", type="concept", estimated_minutes=15),
            JourneyStep(id="dna-4", title="Reading the Code", description="How cells translate DNA sequences into the proteins that run your body", type="concept", estimated_minutes=25),
            JourneyStep(id="dna-5", title="DNA Replication", description="How your cells copy 3 billion base pairs every single time they divide", type="practice", estimated_minutes=20),
            JourneyStep(id="dna-6", title="Mutations & Evolution", description="How tiny copying errors drive the diversity of all life across billions of years", type="explore", estimated_minutes=20),
            JourneyStep(id="dna-7", title="CRISPR: Editing the Code", description="The revolutionary tool that lets scientists rewrite DNA like a text document", type="explore", estimated_minutes=25),
        ],
    ),
    Journey(
        id="journey-ml",
        question="How does machine learning work?",
        title="How Machines Actually Learn",
        description="Strip away the hype — understand the math, patterns, and intuition behind AI with zero jargon.",
        age_group="adults", difficulty="intermediate", estimated_hours=4.0, icon="🤖",
        tags=["AI", "math", "technology"],
        steps=[
            JourneyStep(id="ml-1", title="What is learning, really?", description="Before machines can learn, we need to understand what learning actually means", type="concept", estimated_minutes=15),
            JourneyStep(id="ml-2", title="Data: The Fuel of AI", description="Why garbage in means garbage out — the critical role of training data", type="concept", estimated_minutes=20),
            JourneyStep(id="ml-3", title="Linear Regression", description="The simplest learning algorithm: finding the line that fits the data", type="practice", estimated_minutes=25),
            JourneyStep(id="ml-4", title="Neural Networks from Scratch", description="How layers of simple math can learn to recognize cats, voices, and faces", type="concept", estimated_minutes=30),
            JourneyStep(id="ml-5", title="Training & Gradient Descent", description="The algorithm that nudges a model toward correctness, step by step", type="concept", estimated_minutes=25),
            JourneyStep(id="ml-6", title="Overfitting & Generalization", description="The classic trap — when a model memorizes instead of understanding", type="challenge", estimated_minutes=20),
            JourneyStep(id="ml-7", title="Build a Classifier", description="Apply everything: train a model to classify real data in your browser", type="practice", estimated_minutes=35),
            JourneyStep(id="ml-8", title="Where AI Breaks", description="Bias, hallucinations, and why AI fails — the limits you need to know", type="explore", estimated_minutes=20),
        ],
    ),
    Journey(
        id="journey-rockets",
        question="How do rockets work?",
        title="From Gunpowder to Orbit",
        description="Newton's laws meet engineering to explain how humans punch through Earth's gravity.",
        age_group="all", difficulty="beginner", estimated_hours=2.5, icon="🚀",
        tags=["physics", "engineering", "space"],
        steps=[
            JourneyStep(id="r-1", title="Newton's Third Law", description="Every action has an equal and opposite reaction — the engine of rocketry", type="concept", estimated_minutes=15),
            JourneyStep(id="r-2", title="What is Thrust?", description="How controlled explosions push 500 tons of metal into the sky", type="concept", estimated_minutes=15),
            JourneyStep(id="r-3", title="The Tyranny of the Rocket Equation", description="Why rockets are mostly fuel — the brutal math of getting to orbit", type="concept", estimated_minutes=20),
            JourneyStep(id="r-4", title="Staging: Dropping Dead Weight", description="The clever trick that makes orbital rockets actually possible", type="concept", estimated_minutes=15),
            JourneyStep(id="r-5", title="Orbital Mechanics 101", description="Why you don't fly to space — you fall sideways fast enough to miss the Earth", type="concept", estimated_minutes=20),
            JourneyStep(id="r-6", title="Reusable Rockets", description="How SpaceX and others changed the economics of spaceflight forever", type="explore", estimated_minutes=20),
            JourneyStep(id="r-7", title="Design Your Own Mission", description="Apply the rocket equation to plan a mission to the Moon", type="challenge", estimated_minutes=25),
        ],
    ),
    Journey(
        id="journey-music",
        question="How does music theory work?",
        title="Music Theory Without the Boring Parts",
        description="Why do minor chords feel sad? Why does a melody feel unresolved? Discover the physics of beauty.",
        age_group="all", difficulty="beginner", estimated_hours=3.0, icon="🎵",
        tags=["music", "creativity", "acoustics"],
        steps=[
            JourneyStep(id="m-1", title="What is Sound?", description="Vibrations, frequencies, and why your ear tells a story from air waves", type="concept", estimated_minutes=15),
            JourneyStep(id="m-2", title="The Chromatic Scale", description="The 12 notes that underpin all Western music — and why those 12?", type="concept", estimated_minutes=20),
            JourneyStep(id="m-3", title="Intervals & Tension", description="Why some note pairs feel consonant and others demand resolution", type="concept", estimated_minutes=20),
            JourneyStep(id="m-4", title="Building Chords", description="Stack thirds and you get majors, minors, 7ths — learn the recipe", type="practice", estimated_minutes=25),
            JourneyStep(id="m-5", title="Scales & Keys", description="The selection of notes that gives a piece its emotional home", type="practice", estimated_minutes=20),
            JourneyStep(id="m-6", title="Chord Progressions", description="The IV-V-I resolution that lives in thousands of songs you know", type="explore", estimated_minutes=25),
        ],
    ),
    Journey(
        id="journey-climate",
        question="Why does climate change happen?",
        title="Why Does Climate Change?",
        description="Atmospheric physics, feedback loops, and what the data says — no politics, just the science.",
        age_group="adults", difficulty="intermediate", estimated_hours=3.5, icon="🌍",
        tags=["climate", "science", "environment"],
        steps=[
            JourneyStep(id="c-1", title="The Greenhouse Effect", description="How certain gases trap heat like a blanket around the planet", type="concept", estimated_minutes=20),
            JourneyStep(id="c-2", title="Carbon Dioxide & Methane", description="Why these two molecules punch so far above their weight", type="concept", estimated_minutes=20),
            JourneyStep(id="c-3", title="Reading the Ice Cores", description="800,000 years of climate history locked in Antarctic ice", type="explore", estimated_minutes=20),
            JourneyStep(id="c-4", title="Feedback Loops", description="Melting ice reduces reflectivity, which melts more ice — runaway dynamics explained", type="concept", estimated_minutes=25),
            JourneyStep(id="c-5", title="The Data So Far", description="What global temperature records actually show — the undisputed facts", type="practice", estimated_minutes=20),
            JourneyStep(id="c-6", title="Tipping Points", description="The thresholds scientists worry about — and what crossing them means", type="concept", estimated_minutes=25),
            JourneyStep(id="c-7", title="Solutions Landscape", description="From carbon capture to solar — what the options are and their trade-offs", type="explore", estimated_minutes=20),
        ],
    ),
    Journey(
        id="journey-finance",
        question="How does personal finance work?",
        title="Money: How It Actually Works",
        description="Interest, inflation, and investing — the financial literacy school never taught you.",
        age_group="adults", difficulty="beginner", estimated_hours=2.0, icon="💰",
        tags=["finance", "investing", "life skills"],
        steps=[
            JourneyStep(id="f-1", title="What is Money, Actually?", description="Beyond paper and coins — money as trust, debt, and collective agreement", type="concept", estimated_minutes=15),
            JourneyStep(id="f-2", title="The Time Value of Money", description="Why a dollar today is worth more than a dollar tomorrow", type="concept", estimated_minutes=20),
            JourneyStep(id="f-3", title="Compound Interest", description="Einstein's 'eighth wonder' — the math that makes wealth grow (or debt explode)", type="practice", estimated_minutes=20),
            JourneyStep(id="f-4", title="Inflation & Purchasing Power", description="Why saving cash under a mattress is a guaranteed loss", type="concept", estimated_minutes=15),
            JourneyStep(id="f-5", title="Investing 101", description="Stocks, bonds, index funds — what they are and why diversification matters", type="concept", estimated_minutes=20),
            JourneyStep(id="f-6", title="Build Your First Budget", description="The 50/30/20 rule and how to make it work for your actual life", type="challenge", estimated_minutes=25),
        ],
    ),
]

_journey_map = {j.id: j for j in SAMPLE_JOURNEYS}


def _row_to_journey(row: dict) -> Journey:
    steps_data = row.get("steps") or []
    if isinstance(steps_data, str):
        steps_data = json.loads(steps_data)
    steps = [JourneyStep(**s) for s in steps_data]
    tags = row.get("tags") or []
    return Journey(
        id=row["id"],
        question=row["question"],
        title=row["title"],
        description=row["description"],
        age_group=row.get("age_group", "all"),
        difficulty=row.get("difficulty", "beginner"),
        estimated_hours=row["estimated_hours"],
        steps=steps,
        tags=tags if isinstance(tags, list) else list(tags),
        icon=row.get("icon", "🎯"),
        created_at=str(row.get("created_at", "")),
    )


def _db_journey(journey_id: str) -> Optional[Journey]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM journeys WHERE id = %s", (journey_id,))
                row = cur.fetchone()
                return _row_to_journey(dict(row)) if row else None
    except Exception:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=JourneysResponse, summary="List all journeys")
async def list_journeys(response: Response, uid: Optional[str] = Depends(get_optional_user)):
    user_journeys: list[Journey] = []
    if uid:
        response.headers["Cache-Control"] = "private, max-age=0"
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT * FROM journeys
                        WHERE uid = %s AND is_curated = FALSE
                        ORDER BY created_at DESC
                        """,
                        (uid,),
                    )
                    rows = cur.fetchall()
                    user_journeys = [_row_to_journey(dict(r)) for r in rows]
        except Exception:
            pass
    else:
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"

    all_journeys = user_journeys + SAMPLE_JOURNEYS
    return JourneysResponse(journeys=all_journeys, total=len(all_journeys))


@router.get("/{journey_id}", response_model=Journey, summary="Get a journey by ID")
async def get_journey(journey_id: str, uid: Optional[str] = Depends(get_optional_user)):
    journey = _db_journey(journey_id) or _journey_map.get(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    return journey


class SuggestionsResponse(BaseModel):
    next_level: Optional[Journey] = None
    similar: list[Journey] = []
    next_level_generated: bool = False


@router.get(
    "/{journey_id}/suggestions",
    response_model=SuggestionsResponse,
    summary="Post-completion suggestions: next level + similar journeys, unique to the user",
)
async def journey_suggestions(journey_id: str, uid: str = Depends(get_required_user)):
    source = _db_journey(journey_id) or _journey_map.get(journey_id)
    if not source:
        raise HTTPException(status_code=404, detail="Journey not found")

    # Candidate pool: every stored journey + the curated catalogue.
    pool: list[Journey] = []
    authored_ids: set[str] = set()
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM journeys")
                for r in cur.fetchall():
                    row = dict(r)
                    try:
                        pool.append(_row_to_journey(row))
                    except Exception:
                        continue
                    if row.get("uid") == uid:
                        authored_ids.add(row["id"])
    except Exception:
        logger.exception("suggestions: failed to load journey pool")
    pool.extend(SAMPLE_JOURNEYS)

    # Anything the user has touched is off the table.
    started_ids: set[str] = set()
    source_steps_done = 0
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT journey_id, COUNT(DISTINCT step_id) AS done
                    FROM user_progress WHERE uid = %s GROUP BY journey_id
                    """,
                    (uid,),
                )
                for r in cur.fetchall():
                    started_ids.add(r["journey_id"])
                    if r["journey_id"] == journey_id:
                        source_steps_done = int(r["done"])
    except Exception:
        logger.exception("suggestions: failed to load user progress")
    source_completed = len(source.steps) > 0 and source_steps_done >= len(source.steps)

    next_level, similar = pick_suggestions(
        source=source,
        pool=pool,
        started_ids=started_ids,
        authored_ids=authored_ids,
        curated_ids=set(_journey_map.keys()),
    )

    # On-demand generation costs tokens — only do it once the user has
    # actually finished this journey ("More like this" calls land here too).
    generated = False
    if next_level is None and source_completed:
        next_level = await generate_next_level(uid, source)
        generated = next_level is not None

    return SuggestionsResponse(
        next_level=next_level,
        similar=similar,
        next_level_generated=generated,
    )


@router.get(
    "/{journey_id}/steps/{step_id}/content",
    response_model=StepContentResponse,
    summary="Get or generate step content",
)
async def get_step_content(
    journey_id: str,
    step_id: str,
    uid: str = Depends(get_required_user),
):
    """Returns AI-generated lesson content for a step. Checks cache first."""
    # Check cache
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT content FROM step_content WHERE journey_id = %s AND step_id = %s",
                    (journey_id, step_id),
                )
                cached = cur.fetchone()
                if cached:
                    return StepContentResponse(
                        journey_id=journey_id, step_id=step_id,
                        content=cached["content"], cached=True,
                    )
    except Exception:
        pass

    # Cache miss — check budget before spending tokens
    allowed, reason = check_budget(uid)
    if not allowed:
        raise HTTPException(status_code=402, detail={"error": reason, "upgrade_url": "/pricing"})

    # Resolve journey + step for generation context
    journey = _db_journey(journey_id) or _journey_map.get(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="Journey not found")
    step = next((s for s in journey.steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    try:
        content, in_tok, out_tok = await generate_step_content(
            step_title=step.title,
            step_description=step.description,
            step_type=step.type,
            journey_title=journey.title,
            journey_question=journey.question,
            age_group=journey.age_group,
            uid=uid,
        )
    except ValueError as e:
        logger.warning("step content upstream error", extra={"journey_id": journey_id, "step_id": step_id, "error": str(e)})
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        logger.exception("step content generation failed", extra={"journey_id": journey_id, "step_id": step_id})
        raise HTTPException(status_code=500, detail="Failed to generate step content.")

    record_usage(uid, in_tok, out_tok, get_config("step_content")["model"],
                 interaction_type="step_content")

    # Cache result
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO step_content (journey_id, step_id, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (journey_id, step_id) DO UPDATE SET content = EXCLUDED.content
                    """,
                    (journey_id, step_id, content),
                )
    except Exception:
        pass

    return StepContentResponse(
        journey_id=journey_id, step_id=step_id, content=content, cached=False,
    )
