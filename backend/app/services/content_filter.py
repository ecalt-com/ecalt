"""
Topic scope filter — checked against user-submitted questions before any LLM call.

Blocks requests that have no legitimate educational interpretation: drug synthesis,
weapons manufacturing, violence instructions, CSAM, and specific cybercrime guides.

Design principle: each pattern must be specific enough that no genuine educational
question triggers it.  "How does cocaine affect the brain?" is pharmacology —
it passes.  "How to synthesize cocaine" does not.  The LLM's own safety training
handles the grey area between these two extremes.
"""

_BLOCKED_TOPIC_PATTERNS: list[str] = [
    # ── Drug synthesis / manufacturing ──────────────────────────────────────
    "how to make meth",
    "how to cook meth",
    "how to make methamphetamine",
    "synthesize methamphetamine",
    "how to make cocaine",
    "synthesize cocaine",
    "how to make heroin",
    "synthesize heroin",
    "how to make fentanyl",
    "synthesize fentanyl",
    "how to make crack",
    "how to manufacture drugs",
    "drug synthesis tutorial",
    "clandestine lab setup",
    "make lsd",
    "synthesize lsd",
    "make mdma",
    "synthesize mdma",

    # ── Explosives / weapons manufacturing ──────────────────────────────────
    "how to make a bomb",
    "how to build a bomb",
    "make a bomb",
    "build a bomb",
    "how to make explosives",
    "make explosives",
    "how to make c4",
    "make napalm",
    "how to make napalm",
    "make thermite",
    "how to make thermite",
    "make poison gas",
    "how to make poison gas",
    "how to make a grenade",
    "make a grenade",
    "improvised explosive device tutorial",
    "make an ied",
    "build an ied",
    "construct a bomb",
    "how to make a pipe bomb",
    "pipe bomb instructions",

    # ── Violence / harm instructions (first-person target) ───────────────────
    "how to kill someone",
    "how to murder someone",
    "how to torture someone",
    "how to poison someone",
    "how to hurt someone",
    "how to stalk someone",
    "how to kidnap someone",
    "how to traffick",

    # ── Child sexual exploitation (zero tolerance — any framing) ────────────
    "sexual content involving children",
    "sexual content involving minors",
    "how to groom a child",
    "how to groom children",
    "grooming a minor",
    "child pornography",
    "child sexual abuse",
    "csam",

    # ── Specific cybercrime instructions ────────────────────────────────────
    "how to steal credit cards",
    "how to commit identity theft",
    "how to launder money",
    "how to write malware",
    "how to create ransomware",
    "how to create a virus",
    "how to build a botnet",
    "how to hack into someone",
]

_REFUSAL = (
    "That topic falls outside what ECALT can explore. "
    "Try a different question — there is a whole universe of things to discover."
)


def check_topic_scope(question: str) -> tuple[bool, str]:
    """
    Returns (allowed, refusal_message).
    allowed=True  → question is fine; proceed to LLM.
    allowed=False → blocked; refusal_message is safe to surface to the user.
    """
    lower = question.lower()
    for pattern in _BLOCKED_TOPIC_PATTERNS:
        if pattern in lower:
            return False, _REFUSAL
    return True, ""
