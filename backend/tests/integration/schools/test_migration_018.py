"""#18: migration 018 seeds the school AI config rows with the code defaults,
keeps the code prompts (NULL style_prompt) and never overwrites an admin edit."""
import pathlib

import pytest

from app.services import provider_service as ps

pytestmark = pytest.mark.schools_db

TYPES = ("school_course_outline", "school_step_content", "school_faithfulness_critic")
SQL = (pathlib.Path(__file__).resolve().parents[4] / "migrations" / "018_school_ai_config.sql").read_text()


def _rows(db):
    with db.cursor() as cur:
        cur.execute("SELECT interaction_type, provider, model, style_prompt FROM ai_provider_config "
                    "WHERE interaction_type = ANY(%s)", (list(TYPES),))
        return {r[0]: r[1:] for r in cur.fetchall()}


def test_seed_matches_code_defaults_and_keeps_code_prompts(db):
    with db.cursor() as cur:
        cur.execute(SQL)
        cur.execute(SQL)  # idempotent
    rows = _rows(db)
    for t in TYPES:
        assert rows[t] == (ps.DEFAULT_CONFIG[t]["provider"], ps.DEFAULT_CONFIG[t]["model"], None)
        assert ps.get_config(t)["style_prompt"] == ps.DEFAULT_STYLE_PROMPTS[t]


def test_seed_never_overwrites_an_admin_edit(db):
    with db.cursor() as cur:
        cur.execute("INSERT INTO ai_provider_config (interaction_type, provider, model, style_prompt) "
                    "VALUES ('school_step_content', 'anthropic', 'claude-x', 'custom')")
        cur.execute(SQL)
    assert _rows(db)["school_step_content"] == ("anthropic", "claude-x", "custom")
