# Knowledge Extraction Prompt

**Interaction type:** `knowledge_extraction`
**Default model:** `gpt-4.1-nano`
**Source:** `app/services/knowledge_service.py` — `_EXTRACT_SYSTEM` (line 7)
**Called by:** `extract_knowledge_nodes()` — runs as a background task after every chat turn

---

## System prompt

```
Extract learnable concept-domain pairs from this learning conversation.

Return ONLY a valid JSON array — no markdown, no explanation, just the JSON.

[{"concept": "photosynthesis", "domain": "biology"}, ...]

Rules:
- Extract 0–8 concrete, learnable concepts maximum
- Skip vague words ("things", "stuff", "ideas", "concept")
- Domain must be exactly one of: biology, physics, chemistry, math, history,
  technology, psychology, philosophy, arts, language, economics, engineering, astronomy, medicine
- Return [] if no clear concepts are discussed
```

## User prompt template

```
[CONVERSATION]:
Learner: {user_message[:300]}
Response: {assistant_response[:400]}
```

Input is truncated (user: 300 chars, assistant: 400 chars) before being sent.

## Output

Parsed JSON array of `{concept, domain}` pairs. Each valid pair is upserted into `knowledge_nodes`:
- New concept: strength starts at `0.3`
- Existing concept: strength incremented by `0.15` (capped at `1.0`), `last_reinforced` updated

Max tokens: `300`. Max concepts extracted per call: `8`.

## Valid domains

`biology`, `physics`, `chemistry`, `math`, `history`, `technology`, `psychology`, `philosophy`, `arts`, `language`, `economics`, `engineering`, `astronomy`, `medicine`
