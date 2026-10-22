"""AI course builder — prompt-injection / output hardening (M4 SC-408).

Source documents are untrusted. The generation prompts wrap them in labelled
delimiters, the JSON schema is validated (SC-402/404), and generated text is
stripped of scripts/HTML/links and run through content_filter before it can be
stored or shown to a student.
"""
import json
import re

import pytest

from app.services import school_course_builder as builder  # noqa: F401 - registers handlers
from app.services import school_jobs as sj
from tests.factories import schools as f
from tests.fakes.fake_provider import FakeProvider

pytestmark = pytest.mark.schools_db

_SUPPORTED = json.dumps({"supported": True, "flags": []})


def _sid(w):
    return w.school_a["id"]


def _draft(client, world, jid):
    return client.get(f"/api/v1/schools/{_sid(world)}/courses/{jid}", headers=world.headers("SA")).json()["draft"]


def _unsafe_body(system, user):
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", user)]
    return json.dumps({
        "body_md": ("## Lesson\n\n<script>alert('x')</script>Read [here](http://evil.example/steal) "
                    "and <b>note</b> this ![pic](http://evil.example/p.png). See javascript:void(0)"),
        "citations": ids[:1] or [0], "key_facts": ["A fact"]})


def test_build_strips_scripts_html_and_links_from_bodies(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    (FakeProvider()
        .respond("school_step_content", _unsafe_body)
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/build", json={}, headers=world.headers("SA"))
    assert sj.process_one("w1") is True

    body = _draft(client, world, jid)["steps"][0]["body_md"]
    assert "<script>" not in body and "<b>" not in body
    assert "evil.example" not in body and "javascript:" not in body
    assert "![pic]" not in body and "p.png" not in body
    assert "here" in body and "note" in body       # link/emphasis *text* is kept


def test_build_blocks_bodies_that_fail_the_content_filter(client, world, db, monkeypatch):
    jid = f.make_outlined_draft(db, world.school_a)
    blocked = json.dumps({"body_md": "This paragraph explains how to make a bomb step by step.",
                          "citations": [0], "key_facts": []})
    (FakeProvider()
        .respond("school_step_content", lambda s, u: json.dumps({**json.loads(blocked),
                 "citations": [int(m) for m in re.findall(r"\[(\d+)\]", u)][:1] or [0]}))
        .respond("school_faithfulness_critic", _SUPPORTED)
        .install(monkeypatch))
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/build", json={}, headers=world.headers("SA"))
    sj.process_one("w1")

    draft = _draft(client, world, jid)
    assert draft["status"] == "build_failed"
    assert all(s["build_status"] == "failed" and s["body_md"] is None for s in draft["steps"])


def test_outline_sanitizes_ai_titles_and_descriptions(client, world, db, monkeypatch):
    jid = f.make_course_draft(db, world.school_a)
    outline = json.dumps({"meta": {"title": "Safe <script>x</script> Title"}, "steps": [
        {"title": "Intro <b>bold</b>", "description": "See [link](http://evil.example)",
         "chunk_ids": [0, 1, 2]}], "skipped_sections": []})
    FakeProvider().respond("school_course_outline", outline).install(monkeypatch)
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/outline", json={}, headers=world.headers("SA"))
    sj.process_one("w1")

    step = _draft(client, world, jid)["steps"][0]
    assert step["title"] == "Intro bold" and "<b>" not in step["title"]
    assert "evil.example" not in step["description"] and "link" in step["description"]


def test_source_is_labelled_untrusted_in_the_prompt(client, world, db, monkeypatch):
    jid = f.make_course_draft(db, world.school_a)
    fake = FakeProvider().respond(
        "school_course_outline",
        json.dumps({"meta": {"title": "T"}, "steps": [{"title": "S", "chunk_ids": [0]}], "skipped_sections": []}))
    fake.install(monkeypatch)
    client.post(f"/api/v1/schools/{_sid(world)}/courses/{jid}/outline", json={}, headers=world.headers("SA"))
    sj.process_one("w1")

    prompt = fake.calls_for("school_course_outline")[0].user_content
    assert "SOURCE_BEGIN" in prompt and "SOURCE_END" in prompt
    assert "untrusted" in prompt.lower() and "not instructions" in prompt.lower()
