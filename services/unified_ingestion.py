"""Unified ingestion pipeline with chunked processing and provenance tracking."""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.utils import convert_time_to_seconds
from models.agenda_item import AgendaItem
from models.entity import Entity
from models.mention import Mention
from models.relationship import Relationship
from models.session import Session
from models.speaker import Speaker
from models.video import Video
from parsers.order_paper_parser import OrderPaperParser
from services.chunked_processor import ChunkedTranscriptProcessor, SpeechBlock, Sentence
from services.gemini import GeminiClient
from services.schemas import TRANSCRIPT_SCHEMA
from services.speaker_service import SpeakerService
from services.transcript_models import (
    StructuredTranscript,
    TranscriptAgendaItem,
    TranscriptSentence,
    TranscriptSpeechBlock,
)

settings = get_settings()


@dataclass
class IngestionResult:
    """Result of video ingestion process."""

    session_id: str
    video_id: str
    speakers_created: int = 0
    speakers_matched: int = 0
    agenda_items_created: int = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    mentions_created: int = 0
    errors: list[str] = field(default_factory=list)


class UnifiedIngestionPipeline:
    """
    Unified ingestion pipeline with:
    - Structured transcript extraction (constrained decoding)
    - Speaker deduplication
    - Chunked entity extraction
    - Sentence-level provenance tracking
    """

    def __init__(
        self,
        session: AsyncSession,
        gemini_client: GeminiClient,
    ) -> None:
        """
        Initialize ingestion pipeline.

        Args:
            session: Database session
            gemini_client: Gemini client for LLM operations
        """
        self.session = session
        self.gemini_client = gemini_client
        self.speaker_service = SpeakerService(session)
        self.chunked_processor = ChunkedTranscriptProcessor(gemini_client)

    async def ingest_video(
        self,
        video_url: str,
        video_id: str,
        session_date: date,
        chamber: str,
        sitting_number: str | None = None,
        order_paper_speakers: list[dict] | None = None,
        fps: float = 0.5,
    ) -> IngestionResult:
        """
        Ingest a parliamentary video with full processing pipeline.

        Args:
            video_url: YouTube video URL
            video_id: YouTube video ID
            session_date: Date of the session
            chamber: Chamber ("senate" or "house")
            sitting_number: Sitting number if known
            order_paper_speakers: Known speakers from order paper
            fps: Frames per second for video analysis

        Returns:
            IngestionResult with statistics
        """
        result = IngestionResult(
            session_id=f"s_{sitting_number or 'unknown'}_{session_date.strftime('%Y_%m_%d')}",
            video_id=video_id,
        )

        try:
            # Step 1: Extract structured transcript with constrained decoding
            transcript = await self._extract_transcript(
                video_url=video_url,
                session_date=session_date,
                chamber=chamber,
                sitting_number=sitting_number,
                order_paper_speakers=order_paper_speakers,
                fps=fps,
            )

            # Step 2: Create/update session
            await self._create_session(
                session_id=result.session_id,
                session_date=session_date,
                chamber=chamber,
                sitting_number=sitting_number,
                transcript=transcript,
            )

            # Step 3: Create/update video record
            await self._create_video(
                video_id=video_id,
                session_id=result.session_id,
                video_url=video_url,
                transcript=transcript,
            )

            # Step 4: Process speakers with deduplication
            speaker_stats = await self._process_speakers(
                transcript=transcript,
                chamber=chamber,
                session_id=result.session_id,
            )
            result.speakers_created = speaker_stats["created"]
            result.speakers_matched = speaker_stats["matched"]

            # Step 5: Create agenda items
            await self._create_agenda_items(
                transcript=transcript,
                session_id=result.session_id,
            )
            result.agenda_items_created = len(transcript.agenda_items)

            # Step 6: Extract entities and relationships using chunked processing
            entity_stats = await self._extract_knowledge_graph(
                transcript=transcript,
                session_id=result.session_id,
                video_id=video_id,
            )
            result.entities_extracted = entity_stats["entities"]
            result.relationships_extracted = entity_stats["relationships"]
            result.mentions_created = entity_stats["mentions"]

            await self.session.commit()

        except Exception as e:
            result.errors.append(str(e))
            await self.session.rollback()
            raise

        return result

    async def _extract_transcript(
        self,
        video_url: str,
        session_date: date,
        chamber: str,
        sitting_number: str | None,
        order_paper_speakers: list[dict] | None,
        fps: float,
    ) -> StructuredTranscript:
        """Extract structured transcript using constrained decoding."""
        # Build prompt with context
        speaker_context = ""
        if order_paper_speakers:
            speaker_names = [s.get("name", "") for s in order_paper_speakers]
            speaker_context = f"\n\nExpected speakers: {', '.join(speaker_names)}"

        prompt = f"""Transcribe this Barbados parliamentary session video.

Session Information:
- Date: {session_date.isoformat()}
- Chamber: {chamber}
- Sitting: {sitting_number or "Unknown"}
{speaker_context}

Extract the complete transcript with:
1. **session_title**: Full session title
2. **agenda_items**: List of agenda topics discussed
3. For each agenda item:
   - **topic_title**: Title of the topic
   - **speech_blocks**: Speeches by different speakers
4. For each speech block:
   - **speaker_name**: Name as mentioned in the video
   - **sentences**: Individual sentences with timestamps
5. For each sentence:
   - **start_time**: Timestamp in XmYs format (e.g., "5m30s", "1h15m20s")
   - **text**: The spoken text

Important:
- Use XmYs format for timestamps (e.g., "5m30s" for 5 minutes 30 seconds)
- Preserve speaker names exactly as spoken
- Break speeches into logical sentences
- Include all content without summarization
"""

        # Extract with structured output
        response = self.gemini_client.analyze_video_with_transcript(
            video_url=video_url,
            prompt=prompt,
            response_schema=TRANSCRIPT_SCHEMA,
            fps=fps,
            stage="structured_transcription",
        )

        # Convert to StructuredTranscript
        transcript = StructuredTranscript.from_dict(
            response,
            session_date=session_date,
            chamber=chamber,
            sitting_number=sitting_number,
            video_url=video_url,
        )

        return transcript

    async def _create_session(
        self,
        session_id: str,
        session_date: date,
        chamber: str,
        sitting_number: str | None,
        transcript: StructuredTranscript,
    ) -> None:
        """Create session record."""
        session = Session(
            session_id=session_id,
            date=session_date,
            title=transcript.session_title,
            sitting_number=sitting_number,
            chamber=chamber,
        )
        self.session.add(session)
        await self.session.flush()

    async def _create_video(
        self,
        video_id: str,
        session_id: str,
        video_url: str,
        transcript: StructuredTranscript,
    ) -> None:
        """Create video record."""
        video = Video(
            video_id=video_id,
            session_id=session_id,
            url=video_url,
            platform="youtube",
        )
        self.session.add(video)
        await self.session.flush()

    async def _process_speakers(
        self,
        transcript: StructuredTranscript,
        chamber: str,
        session_id: str,
    ) -> dict[str, int]:
        """Process speakers with deduplication."""
        stats = {"created": 0, "matched": 0}

        # Collect unique speakers from transcript
        unique_speakers: dict[str, str] = {}  # name -> canonical_id

        for agenda_item in transcript.agenda_items:
            for speech_block in agenda_item.speech_blocks:
                speaker_name = speech_block.speaker_name

                if speaker_name not in unique_speakers:
                    # Get or create speaker
                    speaker = await self.speaker_service.get_or_create_speaker(
                        name=speaker_name,
                        chamber=chamber,
                        session_id=session_id,
                    )

                    unique_speakers[speaker_name] = speaker.canonical_id

                    # Update stats: created if this is the first session for this speaker
                    if session_id not in speaker.session_ids:
                        stats["created"] += 1
                    else:
                        stats["matched"] += 1

                # Set canonical ID on speech block
                speech_block.speaker_id = unique_speakers[speaker_name]

        return stats

    async def _create_agenda_items(
        self,
        transcript: StructuredTranscript,
        session_id: str,
    ) -> None:
        """Create agenda item records."""
        for idx, item in enumerate(transcript.agenda_items):
            agenda_item_id = f"{session_id}_a{idx}"

            agenda_item = AgendaItem(
                agenda_item_id=agenda_item_id,
                session_id=session_id,
                agenda_index=idx,
                title=item.topic_title,
            )
            self.session.add(agenda_item)

        await self.session.flush()

    async def _extract_knowledge_graph(
        self,
        transcript: StructuredTranscript,
        session_id: str,
        video_id: str,
    ) -> dict[str, int]:
        """Extract entities and relationships using chunked processing."""
        stats = {"entities": 0, "relationships": 0, "mentions": 0}

        all_entities: list[Entity] = []
        all_relationships: list[Relationship] = []
        all_mentions: list[Mention] = []

        # Process each agenda item
        for agenda_idx, agenda_item in enumerate(transcript.agenda_items):
            # Convert to speech blocks for chunked processor
            speech_blocks = [
                SpeechBlock(
                    speaker_name=block.speaker_name,
                    speaker_id=block.speaker_id,
                    sentences=[
                        Sentence(
                            start_time=s.start_time,
                            text=s.text,
                        )
                        for s in block.sentences
                    ],
                )
                for block in agenda_item.speech_blocks
            ]

            # Process in chunks
            chunk_entities, chunk_relationships = self.chunked_processor.process_transcript(
                agenda_item_title=agenda_item.topic_title,
                speech_blocks=speech_blocks,
            )

            # Convert chunk entities to database entities
            for chunk_entity in chunk_entities:
                entity = await self._get_or_create_entity(chunk_entity)
                all_entities.append(entity)

                # Create mentions for this entity
                for mention_data in chunk_entity.mentions:
                    mention = self._create_mention(
                        entity=entity,
                        mention_data=mention_data,
                        agenda_idx=agenda_idx,
                        speech_blocks=speech_blocks,
                        session_id=session_id,
                        video_id=video_id,
                    )
                    if mention:
                        all_mentions.append(mention)

            # Convert chunk relationships to database relationships
            for chunk_rel in chunk_relationships:
                relationship = self._create_relationship(
                    chunk_rel=chunk_rel,
                    agenda_idx=agenda_idx,
                    speech_blocks=speech_blocks,
                    session_id=session_id,
                    video_id=video_id,
                )
                if relationship:
                    all_relationships.append(relationship)

        stats["entities"] = len(all_entities)
        stats["relationships"] = len(all_relationships)
        stats["mentions"] = len(all_mentions)

        return stats

    async def _get_or_create_entity(
        self,
        chunk_entity: Any,
    ) -> Entity:
        """Get existing entity or create new one."""
        # Check if entity exists
        result = await self.session.execute(
            select(Entity).where(Entity.entity_id == chunk_entity.entity_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Merge aliases
            for alias in chunk_entity.aliases:
                if alias not in existing.aliases:
                    existing.aliases.append(alias)
            return existing

        # Create new entity
        entity = Entity(
            entity_id=chunk_entity.entity_id,
            name=chunk_entity.name,
            canonical_name=chunk_entity.canonical_name,
            entity_type=chunk_entity.entity_type,
            description=chunk_entity.description,
            aliases=chunk_entity.aliases,
            confidence=chunk_entity.confidence,
            source="extraction",
        )
        self.session.add(entity)
        await self.session.flush()
        return entity

    def _create_mention(
        self,
        entity: Entity,
        mention_data: dict,
        agenda_idx: int,
        speech_blocks: list[SpeechBlock],
        session_id: str,
        video_id: str,
    ) -> Mention | None:
        """Create a mention record."""
        sentence_idx = mention_data.get("sentence_index", 0)

        # Find the speech block and sentence
        current_idx = 0
        target_block: SpeechBlock | None = None
        target_sentence: Sentence | None = None
        speech_block_idx = 0

        for sb_idx, block in enumerate(speech_blocks):
            for s_idx, sentence in enumerate(block.sentences):
                if current_idx == sentence_idx:
                    target_block = block
                    target_sentence = sentence
                    speech_block_idx = sb_idx
                    break
                current_idx += 1
            if target_block:
                break

        if not target_block or not target_sentence:
            return None

        # Convert timestamp to seconds
        ts_seconds = convert_time_to_seconds(target_sentence.start_time)

        mention = Mention(
            entity_id=entity.entity_id,
            session_id=session_id,
            video_id=video_id,
            agenda_item_index=agenda_idx,
            speech_block_index=speech_block_idx,
            sentence_index=sentence_idx,
            timestamp=target_sentence.start_time,
            timestamp_seconds=ts_seconds,
            context=target_sentence.text[:200],
            speaker_id=target_block.speaker_id,
            mention_type="direct",
        )
        self.session.add(mention)
        return mention

    def _create_relationship(
        self,
        chunk_rel: Any,
        agenda_idx: int,
        speech_blocks: list[SpeechBlock],
        session_id: str,
        video_id: str,
    ) -> Relationship | None:
        """Create a relationship record with provenance."""
        sentence_idx = chunk_rel.evidence_sentence_index

        # Find the speech block and sentence
        current_idx = 0
        target_block: SpeechBlock | None = None
        target_sentence: Sentence | None = None
        speech_block_idx = 0

        for sb_idx, block in enumerate(speech_blocks):
            for s_idx, sentence in enumerate(block.sentences):
                if current_idx == sentence_idx:
                    target_block = block
                    target_sentence = sentence
                    speech_block_idx = sb_idx
                    break
                current_idx += 1
            if target_block:
                break

        if not target_block or not target_sentence:
            return None

        # Convert timestamp to seconds
        ts_seconds = convert_time_to_seconds(target_sentence.start_time)

        relationship = Relationship(
            source_entity_id=chunk_rel.source_id,
            target_entity_id=chunk_rel.target_id,
            relation=chunk_rel.relation_type,
            sentiment=chunk_rel.sentiment,
            confidence=chunk_rel.confidence,
            evidence_quote=chunk_rel.evidence,
            evidence_timestamp=target_sentence.start_time,
            evidence_timestamp_seconds=ts_seconds,
            session_id=session_id,
            video_id=video_id,
            agenda_item_index=agenda_idx,
            speech_block_index=speech_block_idx,
            sentence_index=sentence_idx,
            source="extraction",
        )
        self.session.add(relationship)
        return relationship
