"""Visual Intelligence Layer (plans/visual-intelligence Phase 4): telemetry
event persistence and the effectiveness rollup formula."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from app.models.visual_schemas import VisualEvent
from app.services import visual_telemetry_service as telemetry


def _fake_db(fetchone_return=None, fetchall_return=None):
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = fetchone_return
    fake_cursor.fetchall.return_value = fetchall_return or []
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor

    @contextmanager
    def fake_get_db():
        yield fake_conn

    return fake_get_db, fake_cursor


class TestRecordEvent:
    def test_writes_expected_columns(self):
        fake_get_db, fake_cursor = _fake_db()
        event = VisualEvent(
            eventType="visual_impression", userId="u1", courseId="j1", lessonId="s1",
            vloId="vlo-1", sessionId="sess-1", eventData={"viewport": "mobile"},
        )
        with patch("app.services.visual_telemetry_service.get_db", fake_get_db):
            telemetry.record_event(event)
        args, _ = fake_cursor.execute.call_args
        _, params = args
        assert params[0] == "u1"
        assert params[1] == "j1"
        assert params[2] == "s1"
        assert params[3] == "vlo-1"
        assert params[4] == "sess-1"
        assert params[5] == "visual_impression"
        assert '"viewport"' in params[6]


class TestEffectivenessSnapshot:
    def test_no_impressions_returns_none_score(self):
        fake_get_db, _ = _fake_db(fetchall_return=[])
        with patch("app.services.visual_telemetry_service.get_db", fake_get_db):
            snapshot = telemetry.vlo_effectiveness_snapshot("vlo-1")
        assert snapshot == {"impressions": 0, "score": None}

    def test_computes_rates_from_counts(self):
        rows = [
            {"event_type": "visual_impression", "n": 10},
            {"event_type": "visual_completed", "n": 6},
            {"event_type": "visual_interaction", "n": 4},
            {"event_type": "visual_replayed", "n": 1},
            {"event_type": "visual_skipped", "n": 2},
        ]
        fake_get_db, _ = _fake_db(fetchall_return=rows)
        with patch("app.services.visual_telemetry_service.get_db", fake_get_db):
            snapshot = telemetry.vlo_effectiveness_snapshot("vlo-1")
        assert snapshot["impressions"] == 10
        assert snapshot["completion_rate"] == 0.6
        assert snapshot["interaction_rate"] == 0.4
        assert snapshot["replay_rate"] == 0.1
        assert snapshot["skip_rate"] == 0.2
        assert snapshot["score"] is not None

    def test_refresh_writes_score_back_when_present(self):
        rows = [{"event_type": "visual_impression", "n": 5}, {"event_type": "visual_completed", "n": 5}]
        fake_get_db, _ = _fake_db(fetchall_return=rows)
        with (
            patch("app.services.visual_telemetry_service.get_db", fake_get_db),
            patch("app.services.visual_telemetry_service.visual_registry_service.set_effectiveness_score") as mock_set,
        ):
            snapshot = telemetry.refresh_effectiveness_score("vlo-1")
        mock_set.assert_called_once()
        assert mock_set.call_args.args[0] == "vlo-1"
        assert snapshot["score"] is not None

    def test_refresh_skips_write_when_no_impressions(self):
        fake_get_db, _ = _fake_db(fetchall_return=[])
        with (
            patch("app.services.visual_telemetry_service.get_db", fake_get_db),
            patch("app.services.visual_telemetry_service.visual_registry_service.set_effectiveness_score") as mock_set,
        ):
            telemetry.refresh_effectiveness_score("vlo-1")
        mock_set.assert_not_called()
