"""
Provider abstraction: Anthropic + OpenAI.
Config is stored in ai_provider_config table so admins can switch live.
"""
from typing import AsyncGenerator

import anthropic
import openai as openai_lib

from app.core.config import settings
from app.core.database import get_db

# ── Available models ──────────────────────────────────────────────────────────

AVAILABLE_MODELS: dict[str, list[dict]] = {
    "anthropic": [
        {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (fast, cheap)"},
        {"id": "claude-sonnet-4-6",          "label": "Claude Sonnet 4.6 (balanced)"},
        {"id": "claude-opus-4-7",            "label": "Claude Opus 4.7 (powerful)"},
    ],
    "openai": [
        {"id": "gpt-4o-mini", "label": "GPT-4o Mini (fast, cheap)"},
        {"id": "gpt-4o",      "label": "GPT-4o (balanced)"},
        {"id": "gpt-4-turbo", "label": "GPT-4 Turbo (powerful)"},
        {"id": "o1-mini",     "label": "o1 Mini (reasoning)"},
    ],
}

# Default config used when DB has no row for an interaction type
DEFAULT_CONFIG: dict[str, dict] = {
    "daily_chat":     {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "nudge":          {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "onboarding":     {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "fingerprint":    {"provider": "anthropic", "model": "claude-sonnet-4-6"},
    "mind_signature": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
}

# Cost per token in cents (input, output)
COST_PER_TOKEN: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-haiku-4-5-20251001": {"input": 0.000080, "output": 0.000400},
    "claude-sonnet-4-6":         {"input": 0.000300, "output": 0.001500},
    "claude-opus-4-7":           {"input": 0.001500, "output": 0.007500},
    # OpenAI
    "gpt-4o-mini":               {"input": 0.000015, "output": 0.000060},
    "gpt-4o":                    {"input": 0.000250, "output": 0.001000},
    "gpt-4-turbo":               {"input": 0.001000, "output": 0.003000},
    "o1-mini":                   {"input": 0.000300, "output": 0.001200},
}

# ── Lazy clients ──────────────────────────────────────────────────────────────

_anthropic_client: anthropic.AsyncAnthropic | None = None
_openai_client: openai_lib.AsyncOpenAI | None = None


def _get_anthropic() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _get_openai() -> openai_lib.AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = openai_lib.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ── DB config helpers ─────────────────────────────────────────────────────────

def get_all_configs() -> list[dict]:
    """Return all rows from ai_provider_config, filling defaults for missing types."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT interaction_type, provider, model FROM ai_provider_config")
                db_rows = {r["interaction_type"]: dict(r) for r in cur.fetchall()}
    except Exception:
        db_rows = {}

    result = []
    for itype, default in DEFAULT_CONFIG.items():
        row = db_rows.get(itype, {})
        result.append({
            "interaction_type": itype,
            "provider": row.get("provider", default["provider"]),
            "model": row.get("model", default["model"]),
        })
    return result


def get_config(interaction_type: str) -> dict:
    """Return provider + model for an interaction type."""
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT provider, model FROM ai_provider_config WHERE interaction_type = %s",
                    (interaction_type,),
                )
                row = cur.fetchone()
                if row:
                    return {"provider": row["provider"], "model": row["model"]}
    except Exception:
        pass
    return DEFAULT_CONFIG.get(interaction_type, DEFAULT_CONFIG["daily_chat"])


def set_config(interaction_type: str, provider: str, model: str) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_provider_config (interaction_type, provider, model)
                VALUES (%s, %s, %s)
                ON CONFLICT (interaction_type) DO UPDATE SET
                    provider   = EXCLUDED.provider,
                    model      = EXCLUDED.model,
                    updated_at = now()
                """,
                (interaction_type, provider, model),
            )


def cost_for_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in cents."""
    rates = COST_PER_TOKEN.get(model, {"input": 0.000080, "output": 0.000400})
    return (input_tokens * rates["input"]) + (output_tokens * rates["output"])


# ── Streaming abstraction ─────────────────────────────────────────────────────

async def stream_completion(
    provider: str,
    model: str,
    system: str,
    messages: list[dict],
    max_tokens: int = 1024,
) -> AsyncGenerator[tuple[str, int, int], None]:
    """
    Yields (text_chunk, input_tokens, output_tokens).
    input_tokens / output_tokens are only non-zero on the final yield.
    """
    if provider == "openai":
        async for item in _stream_openai(model, system, messages, max_tokens):
            yield item
    else:
        async for item in _stream_anthropic(model, system, messages, max_tokens):
            yield item


async def _stream_anthropic(
    model: str, system: str, messages: list[dict], max_tokens: int
) -> AsyncGenerator[tuple[str, int, int], None]:
    input_tokens = output_tokens = 0
    async with _get_anthropic().messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text, 0, 0
        final = await stream.get_final_message()
        input_tokens = final.usage.input_tokens
        output_tokens = final.usage.output_tokens
    yield "", input_tokens, output_tokens


async def _stream_openai(
    model: str, system: str, messages: list[dict], max_tokens: int
) -> AsyncGenerator[tuple[str, int, int], None]:
    oai_messages = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        # Flatten structured content blocks to plain text for OpenAI
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        oai_messages.append({"role": m["role"], "content": content})

    input_tokens = output_tokens = 0
    # o1 models don't support streaming or system messages the same way
    if model.startswith("o1"):
        oai_messages_no_sys = [m for m in oai_messages if m["role"] != "system"]
        resp = await _get_openai().chat.completions.create(
            model=model,
            messages=oai_messages_no_sys,
            max_completion_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        input_tokens = resp.usage.prompt_tokens if resp.usage else 0
        output_tokens = resp.usage.completion_tokens if resp.usage else 0
        yield text, 0, 0
        yield "", input_tokens, output_tokens
        return

    stream = await _get_openai().chat.completions.create(
        model=model,
        messages=oai_messages,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content, 0, 0
        if chunk.usage:
            input_tokens = chunk.usage.prompt_tokens
            output_tokens = chunk.usage.completion_tokens
    yield "", input_tokens, output_tokens
