"""Video ingestion tests for new schema"""

from datetime import date, datetime, timezone
from typing import Any, cast
from unittest.mock import Mock
import pytest
from sqlalchemy import select

from models.entity import Entity
from models.relationship import Relationship
from models.relationship_evidence import RelationshipEvidence
from models.speaker import Speaker
from models.transcript_segment import TranscriptSegment
from models.video import Video
from models.session import Session as SessionModel
from models.agenda_item import AgendaItem
from parsers.transcript_models import (
    Sentence,
    SessionTranscript,
    SpeechBlock,
    TranscriptAgendaItem,
)
from scripts.ingest_video import VideoIngestor
from services.entity_extractor import ExtractionResult, ExtractedRelationship
from services.gemini import GeminiClient


class StubTranscriptionService:
    """Stub transcription service for tests."""

    def __init__(self, transcript: SessionTranscript):
        self._transcript = transcript

    def _parse_response(self, response):
        return self._transcript


class StubEntityExtractor:
    """Stub entity extractor for tests."""

    def __init__(self, extraction: ExtractionResult):
        self._extraction = extraction

    def extract_from_transcript(self, transcript):
        return self._extraction


class StubEmbeddingService:
    """Stub embedding service for tests."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions
        self.calls = []
        self.model_name = "test-model"
        self.model_version = "test-version"

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.0 for _ in range(self.dimensions)] for _ in texts]


@pytest.mark.asyncio
async def test_ingest_video_creates_session_and_video(db_session):
    """Ingesting a video should create Session and Video records with stable IDs."""
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Agenda 1",
                bill_id="bill1",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. John Smith",
                        speaker_id="hon_john_smith",
                        sentences=[Sentence(start_time="0m5s0ms", text="Good morning.")],
                    )
                ],
            )
        ],
    )

    extraction = ExtractionResult(
        session_id="s_10_2026_01_06",
        entities=[
            Entity(
                entity_id="hon_john_smith",
                name="John Smith",
                canonical_name="John Smith",
                entity_type="person",
                entity_subtype="speaker",
                description="Speaker",
                aliases=[],
                importance_score=1.0,
                source="test",
                source_ref="s_10_2026_01_06",
            )
        ],
        relationships=[],
    )

    ingestor = VideoIngestor(
        db_session,
        gemini_client=Mock(spec=GeminiClient),
    )
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService())

    result = await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=test123",
        chamber="house",
        session_date=date(2026, 1, 6),
        sitting_number="10",
    )

    assert result["status"] == "success"

    session = await db_session.execute(
        select(SessionModel).where(SessionModel.session_id == "s_10_2026_01_06")
    )
    session = session.scalar_one()
    assert session is not None
    assert session.chamber == "house"
    assert session.sitting_number == "10"

    video = await db_session.execute(select(Video).where(Video.video_id == "test123"))
    video = video.scalar_one()
    assert video is not None
    assert video.session_id == "s_10_2026_01_06"
    assert video.platform == "youtube"


@pytest.mark.asyncio
async def test_ingest_video_creates_agenda_items(db_session):
    """Ingesting should create agenda items with stable IDs."""
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="First Agenda Item",
                bill_id="bill1",
                speech_blocks=[],
            ),
            TranscriptAgendaItem(
                topic_title="Second Agenda Item",
                bill_id="bill2",
                speech_blocks=[],
            ),
        ],
    )

    extraction = ExtractionResult(
        session_id="s_10_2026_01_06",
        entities=[],
        relationships=[],
    )

    ingestor = VideoIngestor(
        db_session,
        gemini_client=Mock(spec=GeminiClient),
    )
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService())

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=test123",
        chamber="house",
        session_date=date(2026, 1, 6),
        sitting_number="10",
    )

    agenda1 = await db_session.execute(
        select(AgendaItem).where(AgendaItem.agenda_item_id == "s_10_2026_01_06_a0")
    )
    agenda1 = agenda1.scalar_one()
    assert agenda1 is not None
    assert agenda1.title == "First Agenda Item"
    assert agenda1.agenda_index == 0

    agenda2 = await db_session.execute(
        select(AgendaItem).where(AgendaItem.agenda_item_id == "s_10_2026_01_06_a1")
    )
    agenda2 = agenda2.scalar_one()
    assert agenda2 is not None
    assert agenda2.title == "Second Agenda Item"
    assert agenda2.agenda_index == 1


@pytest.mark.asyncio
async def test_ingest_video_creates_transcript_segments_with_stable_ids(db_session):
    """Ingesting should create transcript segments with format {youtube_id}_{start:05d}."""
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="First Agenda",
                bill_id="bill1",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Speaker",
                        speaker_id="p_speaker",
                        sentences=[
                            Sentence(start_time="0m5s0ms", text="First sentence."),
                            Sentence(start_time="0m10s0ms", text="Second sentence."),
                        ],
                    )
                ],
            )
        ],
    )

    extraction = ExtractionResult(
        session_id="s_10_2026_01_06",
        entities=[],
        relationships=[],
    )

    ingestor = VideoIngestor(
        db_session,
        gemini_client=Mock(spec=GeminiClient),
    )
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService())

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=test123",
        chamber="house",
        session_date=date(2026, 1, 6),
        sitting_number="10",
    )

    segments = await db_session.execute(
        select(TranscriptSegment).where(TranscriptSegment.video_id == "test123")
    )
    segments = segments.scalars().all()

    assert len(segments) == 2

    segment_ids = [s.segment_id for s in segments]
    assert "test123_00005" in segment_ids
    assert "test123_00010" in segment_ids


@pytest.mark.asyncio
async def test_ingest_video_creates_relationship_evidence(db_session):
    """Ingesting with relationships should create RelationshipEvidence rows."""
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="First Agenda",
                bill_id="bill1",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Speaker",
                        speaker_id="p_speaker",
                        sentences=[
                            Sentence(start_time="0m5s0ms", text="The bill amends the act."),
                            Sentence(
                                start_time="0m10s0ms",
                                text="This is important legislation.",
                            ),
                        ],
                    )
                ],
            )
        ],
    )

    extraction = ExtractionResult(
        session_id="s_10_2026_01_06",
        entities=[
            Entity(
                entity_id="bill1",
                name="Bill 1",
                canonical_name="Bill 1",
                entity_type="legislation",
                entity_subtype="bill",
                description="Test bill",
                aliases=[],
                importance_score=0.5,
                source="test",
                source_ref="s_10_2026_01_06",
            ),
            Entity(
                entity_id="act1",
                name="Act 1",
                canonical_name="Act 1",
                entity_type="legislation",
                entity_subtype="act",
                description="Test act",
                aliases=[],
                importance_score=0.5,
                source="test",
                source_ref="s_10_2026_01_06",
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_id="bill1",
                target_id="act1",
                relation_type="amends",
                evidence="The bill amends the act.",
                confidence=0.9,
                source="test",
                source_ref="s_10_2026_01_06",
            ),
        ],
    )

    ingestor = VideoIngestor(
        db_session,
        gemini_client=Mock(spec=GeminiClient),
    )
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService())

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=test123",
        chamber="house",
        session_date=date(2026, 1, 6),
        sitting_number="10",
    )

    evidence = await db_session.execute(
        select(RelationshipEvidence).where(RelationshipEvidence.video_id == "test123")
    )
    evidence = evidence.scalars().all()

    assert len(evidence) > 0

    relationship = await db_session.execute(
        select(Relationship).where(Relationship.source_entity_id == "bill1")
    )
    relationship = relationship.scalar_one()
    assert relationship is not None
    assert relationship.source_entity_id == "bill1"
    assert relationship.target_entity_id == "act1"
    assert relationship.relation == "amends"


@pytest.mark.asyncio
async def test_ingest_video_skips_existing_video(db_session):
    """Ingesting should skip videos that already exist."""
    video = Video(
        video_id="test123",
        session_id="s_10_2026_01_06",
        platform="youtube",
        url="https://www.youtube.com/watch?v=test123",
        duration_seconds=None,
    )
    session = SessionModel(
        session_id="s_10_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House Session",
        sitting_number="10",
        chamber="house",
    )
    db_session.add(session)
    db_session.add(video)
    await db_session.commit()

    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[],
    )

    extraction = ExtractionResult(
        session_id="s_10_2026_01_06",
        entities=[],
        relationships=[],
    )

    ingestor = VideoIngestor(
        db_session,
        gemini_client=Mock(spec=GeminiClient),
    )
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService())

    result = await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=test123",
        chamber="house",
        session_date=date(2026, 1, 6),
        sitting_number="10",
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "already_exists"
