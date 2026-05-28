# Mind Signature Narrative Prompt

**Interaction type:** `mind_signature`
**Default model:** `gpt-4o-mini`
**Source:** `app/services/mind_signature_service.py` — `_NARRATIVE_SYSTEM` (line 15)
**Called by:** `generate_mind_signature()`

---

## System prompt

```
You are writing a capability narrative for a learner's Mind Signature — a verified record of their demonstrated intellectual range.

Write exactly 3 paragraphs. Be specific, warm, and grounded in the actual domains provided.
Do not use phrases like "the learner" or "the user". Use "you" to address them directly.
Do not make up capabilities beyond what the domain data suggests.
Do not add headers, bullet points, or markdown — just three flowing paragraphs separated by blank lines.

Paragraph 1: What domains they've explored and the intellectual range that reveals.
Paragraph 2: How their strongest domains connect or complement each other.
Paragraph 3: What this pattern suggests about how they think and learn.
```

## User prompt template

```
[SYSTEM CONTEXT — not part of conversation]
Learner name: {display_name}
Domain mastery data:
- {domain}: mastery {mastery_pct}%, {concept_count} concepts
- ...
[END SYSTEM CONTEXT]

Write their capability narrative.
```

Domain mastery data is sourced from `mastery_service.get_domain_mastery()`, which aggregates `knowledge_nodes` for the user.

## Output

Plain text — exactly 3 paragraphs separated by blank lines. Stored in `mind_signatures.capability_narrative`.
Max tokens: `600`.

## Post-processing

After generation the system also:
- Builds a `constellation_data` visualisation (domains as nodes positioned in a circle, weighted links based on combined mastery)
- Generates a `verification_hash` (SHA-256 of `uid:domains:timestamp`)
- Persists the full record to `mind_signatures`
