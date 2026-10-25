"""School students get tutoring, not profiling (compliance memo §6, DPDP s. 9(3)).

After a tutor turn, an ordinary learner's conversation feeds knowledge-node
extraction, the cognitive fingerprint and a re-engagement nudge. For a school
student only usage metering runs.
"""
import asyncio
from unittest.mock import AsyncMock, patch


def _run_bg(uid: str):
    from app.services import chat_service
    recorded, extracted, fingerprinted, nudged = [], AsyncMock(), AsyncMock(), AsyncMock()

    async def run():
        with patch("app.services.subscription_service.record_usage",
                   side_effect=lambda *a, **kw: recorded.append(a[0])), \
             patch("app.services.knowledge_service.extract_knowledge_nodes", extracted), \
             patch("app.services.fingerprint_service.get_fingerprint", return_value=None, create=True), \
             patch.object(chat_service, "update_fingerprint", fingerprinted), \
             patch.object(chat_service, "_queue_cliffhanger", nudged), \
             patch.object(chat_service, "get_db") as get_db:
            cur = get_db.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cur.fetchone.return_value = {"cnt": 2}     # an even turn → fingerprint would update
            await chat_service._post_stream_bg(
                uid=uid, conv_id="c1", user_message="why is the sky blue", assistant_response="…",
                model="gpt-4o-mini", input_tokens=10, output_tokens=5,
                interaction_type="journey_tutor", journey_id="j1")

    asyncio.run(run())
    return recorded, extracted, fingerprinted, nudged


def test_school_student_turn_only_records_usage():
    recorded, extracted, fingerprinted, nudged = _run_bg("stu_0123456789abcdef")
    assert recorded == ["stu_0123456789abcdef"]
    extracted.assert_not_called()
    fingerprinted.assert_not_called()
    nudged.assert_not_called()


def test_ordinary_learner_turn_still_runs_the_full_pipeline():
    recorded, extracted, fingerprinted, nudged = _run_bg("user_abc")
    assert recorded == ["user_abc"]
    extracted.assert_awaited_once()
    nudged.assert_awaited_once()
    fingerprinted.assert_awaited_once()
