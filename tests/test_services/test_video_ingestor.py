"""Video ingestion tests."""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from models.entity import Entity
from models.mention import Mention
from models.relationship import Relationship
from models.speaker import Speaker
from models.transcript_segment import TranscriptSegment
from models.video import Video as VideoModel
from parsers.models import AgendaItem, OrderPaper, OrderPaperSpeaker
from parsers.transcript_models import (
    Sentence,
    SessionTranscript,
    SpeechBlock,
    TranscriptAgendaItem,
)
from scripts.ingest_video import VideoIngestor
from services.entity_extractor import ExtractionResult
from services.gemini import GeminiClient
from services.video_transcription import VideoTranscriptionService


class StubTranscriptionService:
    """Stub transcription service for tests."""

    def __init__(self, transcript: SessionTranscript):
        self._transcript = transcript

    def transcribe(self, video_url: str, order_paper: OrderPaper, speaker_id_mapping: dict):
        return self._transcript


class StubEntityExtractor:
    """Stub entity extractor for tests."""

    def __init__(self, extraction: ExtractionResult):
        self._extraction = extraction

    def extract_from_transcript(self, transcript):
        return self._extraction


class StubEmbeddingService:
    """Stub embedding service for tests."""

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions
        self.calls = []
        self.model_name = "test-model"
        self.model_version = "test-version"

    def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.0 for _ in range(self.dimensions)] for _ in texts]


@pytest.mark.asyncio
async def test_ingest_video_updates_existing_without_transcript(db_session):
    """Existing videos without transcripts should be updated."""
    video = VideoModel(
        youtube_id="abc123",
        youtube_url="https://www.youtube.com/watch?v=abc123",
        title="Placeholder",
        chamber="house",
        session_date=datetime.now(timezone.utc).replace(tzinfo=None),
        transcript={},
    )
    db_session.add(video)
    await db_session.commit()

    order_paper = OrderPaper(
        session_title="Test Session",
        session_date=datetime.now(timezone.utc).date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Intro")],
    )
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
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
        session_date=datetime.now(timezone.utc).replace(tzinfo=None),
        transcript={},
    )
    db_session.add(video)
    await db_session.commit()

    order_paper = OrderPaper(
        session_title="Stored Session",
        session_date=datetime.now(timezone.utc).date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Intro")],
    )
    transcript = SessionTranscript(
        session_title="Stored Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
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


@pytest.mark.asyncio
async def test_ingest_video_persists_speaker_entities(db_session):
    """Speaker entities should be stored in the knowledge graph."""
    order_paper = OrderPaper(
        session_title="Speaker Session",
        session_date=datetime.now(timezone.utc).date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Intro")],
    )
    transcript = SessionTranscript(
        session_title="Speaker Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[],
    )

    speaker_entity = Entity(
        entity_id="speaker-123",
        entity_type="person",
        name="Hon. Jane Doe",
        canonical_name="Hon. Jane Doe",
        aliases=[],
        description="Parliamentary speaker",
        importance_score=1.0,
    )
    extraction = ExtractionResult(
        session_id="house-2024-01-01",
        entities=[speaker_entity],
        relationships=[],
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, Mock()))
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService(dimensions=768))

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=speaker123",
        order_paper=order_paper,
    )

    result = await db_session.execute(select(Entity).where(Entity.entity_id == "speaker-123"))
    entity = result.scalar_one_or_none()

    assert entity is not None


@pytest.mark.asyncio
async def test_ingest_video_creates_mentions_and_agenda_edges(db_session):
    """Ingest should create mentions and agenda-based relationships."""
    db_session.add(
        Speaker(
            canonical_id="jane-doe",
            name="Hon. Jane Doe",
            title="Hon.",
            role="Minister of Transport",
            aliases=[],
            meta_data={},
        )
    )
    await db_session.commit()

    order_paper = OrderPaper(
        session_title="KG Session",
        session_date=datetime.now(timezone.utc).date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Road Traffic Bill")],
    )
    transcript = SessionTranscript(
        session_title="KG Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Road Traffic Bill",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Jane Doe",
                        speaker_id="jane-doe",
                        sentences=[
                            Sentence(
                                start_time="0m0s0ms",
                                text="The Road Traffic Act, Cap. 295 will be amended.",
                            )
                        ],
                    )
                ],
            )
        ],
    )

    extracted_entity = Entity(
        entity_id="road-traffic-act-cap-295",
        entity_type="law",
        name="Road Traffic Act, Cap. 295",
        canonical_name="Road Traffic Act, Chapter 295",
        aliases=["the Act"],
        description="Primary traffic legislation",
        importance_score=0.7,
    )
    extraction = ExtractionResult(
        session_id="house-2024-01-01",
        entities=[extracted_entity],
        relationships=[],
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, Mock()))
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService(dimensions=768))

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=kg123",
        order_paper=order_paper,
    )

    mention_result = await db_session.execute(
        select(Mention).where(Mention.entity_id == "road-traffic-act-cap-295")
    )
    mention = mention_result.scalar_one_or_none()

    assert mention is not None
    assert mention.agenda_item_index == 0
    assert mention.speech_block_index == 0
    assert mention.sentence_index == 0
    assert mention.speaker_id == "jane-doe"

    agenda_result = await db_session.execute(
        select(Entity).where(Entity.entity_type == "agenda_item")
    )
    agenda_entity = agenda_result.scalar_one_or_none()

    assert agenda_entity is not None
    assert agenda_entity.name == "Road Traffic Bill"

    relationship_result = await db_session.execute(
        select(Relationship).where(Relationship.relation_type.in_(["speaks_on", "about"]))
    )
    relationships = relationship_result.scalars().all()

    assert len(relationships) == 2


@pytest.mark.asyncio
async def test_ingest_video_persists_transcript_segments(db_session):
    """Transcript segments should be stored with embeddings."""
    order_paper = OrderPaper(
        session_title="Segment Session",
        session_date=datetime.now(timezone.utc).date(),
        speakers=[OrderPaperSpeaker(name="Hon. Jane Doe")],
        agenda_items=[AgendaItem(topic_title="Segment Topic")],
    )
    transcript = SessionTranscript(
        session_title="Segment Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Segment Topic",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Jane Doe",
                        speaker_id="jane-doe",
                        sentences=[
                            Sentence(start_time="0m0s0ms", text="Sentence one."),
                            Sentence(start_time="0m5s0ms", text="Sentence two."),
                        ],
                    )
                ],
            )
        ],
    )

    extraction = ExtractionResult(
        session_id="house-2024-01-01",
        entities=[],
        relationships=[],
    )

    ingestor = VideoIngestor(db_session, gemini_client=cast(GeminiClient, Mock()))
    ingestor.transcription_service = cast(Any, StubTranscriptionService(transcript))
    ingestor.entity_extractor = cast(Any, StubEntityExtractor(extraction))
    ingestor.embedding_service = cast(Any, StubEmbeddingService(dimensions=768))

    await ingestor.ingest_video(
        youtube_url="https://www.youtube.com/watch?v=segment123",
        order_paper=order_paper,
    )

    result = await db_session.execute(select(TranscriptSegment))
    segments = result.scalars().all()

    assert len(segments) == 1
    assert segments[0].embedding is not None
