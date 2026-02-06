"""Tests for session ID generation in ingest_video."""

from datetime import datetime, timezone

from scripts import ingest_video
from scripts.ingest_video import VideoIngestor


def test_generate_session_id_uses_current_date_when_missing(mock_db, monkeypatch):
    """Missing session date should use current UTC date."""

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 1, 2, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(ingest_video, "datetime", FixedDateTime)

    ingestor = VideoIngestor(db_session=mock_db, gemini_client=None)

    session_id = ingestor._generate_session_id("house", None, None)

    assert session_id == "s_0_2026_01_02"
