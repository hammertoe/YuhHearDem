"""Video ingestion tests."""

from datetime import datetime
from typing import Any, cast
from unittest.mock import Mock

import pytest

from models.video import Video as VideoModel
from parsers.models import AgendaItem, OrderPaper, OrderPaperSpeaker
from parsers.transcript_models import SessionTranscript
from scripts.ingest_video import VideoIngestor
from services.gemini import GeminiClient
from services.video_transcription import VideoTranscriptionService


class StubTranscriptionService:
    """Stub transcription service for tests."""

    def __init__(self, transcript: SessionTranscript):
        self._transcript = transcript

    def transcribe(self, video_url: str, order_paper: OrderPaper, speaker_id_mapping: dict):
        return self._transcript


@pytest.mark.asyncio
async def test_ingest_video_updates_existing_without_transcript(db_session):
    """Existing videos without transcripts should be updated."""
    video = VideoModel(
        youtube_id="abc123",
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Placeholder",
        chamber="house",
        session_date=datetime.utcnow(),
        transcript={},
    )
    db_session.add(video)
    await db_session.commit()

    order_paper = OrderPaper(
        session_title="Test Session",
        session_date=datetime.utcnow().date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Intro")],
    )
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.utcnow(),
        chamber="house",
        agenda_items=[],
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, Mock()))
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))

    result = await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=abc123",
        order_paper=order_paper,
    )

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_ingest_video_saves_transcript_dict(db_session):
    """Transcripts are persisted as dictionaries."""
    video = VideoModel(
        youtube_id="def456",
        youtube_url="https://www.youtube.com/watch?v=def456",
        title="Placeholder",
        chamber="house",
        session_date=datetime.utcnow(),
        transcript={},
    )
    db_session.add(video)
    await db_session.commit()

    order_paper = OrderPaper(
        session_title="Stored Session",
        session_date=datetime.utcnow().date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Intro")],
    )
    transcript = SessionTranscript(
        session_title="Stored Session",
        date=datetime.utcnow(),
        chamber="house",
        agenda_items=[],
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, Mock()))
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=def456",
        order_paper=order_paper,
    )

    await db_session.refresh(video)

    assert video.transcript["session_title"] == "Stored Session"


@pytest.mark.asyncio
async def test_ingest_video_without_order_paper_uses_schema(db_session):
    """Transcription requests should include response schema."""
    mock_client = Mock()
    mock_client.analyze_video_with_transcript = Mock(
        return_value={
            "title": "No Order Paper Session",
            "video_url": "https://example.com",
            "video_title": "Example",
        }
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, mock_client))

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=xyz789",
        chamber="house",
    )

    _, kwargs = mock_client.analyze_video_with_transcript.call_args

    assert kwargs["response_schema"] == VideoTranscriptionService.TRANSCRIPT_SCHEMA
