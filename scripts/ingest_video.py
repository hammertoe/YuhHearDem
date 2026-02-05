#!/usr/bin/env python3
"""Ingest videos to database with transcription"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.dependencies import get_db_session
from models.entity import Entity
from models.relationship import Relationship
from models.speaker import Speaker
from models.video import Video as VideoModel
from models.mention import Mention
from models.transcript_segment import TranscriptSegment
from parsers.models import OrderPaper as ParsedOrderPaper
from parsers.transcript_models import SessionTranscript
from services.embeddings import EmbeddingService
from services.entity_extractor import EntityExtractor
from services.gemini import GeminiClient
from services.transcript_segmenter import TranscriptSegmentData, TranscriptSegmenter
from services.video_transcription import VideoTranscriptionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VideoIngestor:
    """Ingests videos into database"""

    def __init__(
        self,
        db_session: AsyncSession,
        gemini_client: GeminiClient,
        entity_extractor: "EntityExtractor | None" = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.db = db_session
        self.client = gemini_client
        self.transcription_service = VideoTranscriptionService(gemini_client)
        self.entity_extractor = entity_extractor
        self.embedding_service = embedding_service or EmbeddingService(gemini_client=gemini_client)
        self.stage_timings_ms: dict[str, float] = {}

    async def ingest_video(
        self,
        youtube_url: str,
        chamber: str = "house",
        session_date: datetime | None = None,
        sitting_number: str | None = None,
        order_paper: ParsedOrderPaper | None = None,
        fps: float | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict:
        """
        Transcribe and save a video.

        Args:
            youtube_url: YouTube URL
            chamber: 'house' or 'senate'
            session_date: Session date
            sitting_number: Sitting number
            order_paper: Parsed order paper for context (optional)

        Returns:
            Dictionary with ingest status and IDs
        """

        overall_start = time.perf_counter()
        youtube_id = self._extract_youtube_id(youtube_url)

        logger.info(f"Ingesting video: {youtube_id}")

        # Check if already exists
        existing = await self.db.execute(
            select(VideoModel).where(VideoModel.youtube_id == youtube_id)
        )
        video = existing.scalar_one_or_none()
        if video and video.transcript and video.transcript_processed_at:
            logger.info(f"Video already exists with transcript: {youtube_id}")
            return {"status": "skipped", "reason": "already_exists"}

        try:
            # Build speaker ID mapping from database
            speaker_id_mapping = await self._get_speaker_id_mapping()

            # Transcribe video
            transcript: SessionTranscript
            transcribe_start = time.perf_counter()
            if order_paper:
                effective_fps = fps if fps is not None else 0.25
                transcript = self.transcription_service.transcribe(
                    video_url=youtube_url,
                    order_paper=order_paper,
                    speaker_id_mapping=speaker_id_mapping,
                    fps=effective_fps,
                    start_time=start_time,
                    end_time=end_time,
                )
            else:
                # Transcribe without order paper context
                logger.warning("Transcribing without order paper - results may be less accurate")
                prompt = """Transcribe this Barbados parliamentary session.

        STRUCTURE:
        1. Group by agenda items naturally
        2. For each speech block:
           - speaker_name: Name as spoken
           - sentences: List of sentences with timestamps
        3. Timestamp format: XmYsZms (e.g., 0m5s250ms)

        INSTRUCTIONS:
        - Preserve parliamentary language and formal tone
        - Identify speaker changes clearly
        - Include all content"""

                response = self.client.analyze_video_with_transcript(
                    video_url=youtube_url,
                    prompt=prompt,
                    response_schema=VideoTranscriptionService.TRANSCRIPT_SCHEMA,
                    fps=fps if fps is not None else 0.25,
                    start_time=start_time,
                    end_time=end_time,
                )

                transcript = self._parse_simple_response(response)
            self.stage_timings_ms["transcription"] = (time.perf_counter() - transcribe_start) * 1000

            transcript = cast(SessionTranscript, transcript)

            entities_count = 0
            extraction = None
            if self.entity_extractor and hasattr(self.entity_extractor, "extract_from_transcript"):
                try:
                    extraction_start = time.perf_counter()
                    extraction = self.entity_extractor.extract_from_transcript(transcript)
                    entities_count = len(extraction.entities)
                    self.stage_timings_ms["kg_extraction"] = (
                        time.perf_counter() - extraction_start
                    ) * 1000
                except Exception as exc:
                    logger.warning(f"Entity extraction failed: {exc}")

            if extraction is None:
                from services.entity_extractor import ExtractionResult

                extraction = ExtractionResult(
                    session_id=f"{transcript.chamber}-{transcript.date.isoformat()}",
                    entities=[],
                    relationships=[],
                )

            # Save to database
            transcript_data = self._serialize_transcript(transcript)
            if video is None:
                video = VideoModel(
                    youtube_id=youtube_id,
                    youtube_url=youtube_url,
                    title=transcript.session_title or f"Session {youtube_id}",
                    chamber=chamber,
                    session_date=session_date or datetime.now(timezone.utc).replace(tzinfo=None),
                    sitting_number=sitting_number,
                    transcript=transcript_data,
                    transcript_processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                self.db.add(video)
            else:
                video.youtube_url = youtube_url
                video.title = transcript.session_title or video.title
                video.chamber = chamber
                video.session_date = session_date or video.session_date
                video.sitting_number = sitting_number
                video.transcript = transcript_data
                video.transcript_processed_at = datetime.now(timezone.utc).replace(tzinfo=None)

            await self.db.flush()

            speaker_lookup = await self._get_speaker_lookup()
            segment_start = time.perf_counter()
            segments, sentence_segment_map = self._segment_transcript(transcript, speaker_lookup)
            await self._replace_segments(video, segments)
            self.stage_timings_ms["segment_embedding"] = (
                time.perf_counter() - segment_start
            ) * 1000

            if extraction:
                persist_start = time.perf_counter()
                await self._persist_knowledge_graph(
                    video,
                    transcript,
                    extraction,
                    sentence_segment_map,
                )
                self.stage_timings_ms["kg_persist"] = (time.perf_counter() - persist_start) * 1000

            await self.db.commit()
            await self.db.refresh(video)

            self.stage_timings_ms["total"] = (time.perf_counter() - overall_start) * 1000
            self._log_run_summary(youtube_id)
            logger.info(f"Saved video: {video.id}")

            return {
                "status": "success",
                "video_id": str(video.id),
                "youtube_id": youtube_id,
                "entities_count": entities_count,
            }

        except Exception as e:
            logger.error(f"Failed to ingest video: {e}")
            await self.db.rollback()
            return {"status": "error", "error": str(e)}

    async def ingest_from_file(
        self,
        mapping_file: Path,
        fps: float | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict]:
        """
        Ingest videos from a JSON mapping file.

        Args:
            mapping_file: JSON file with video metadata
            fps: Optional FPS override
            start_time: Optional start time in seconds
            end_time: Optional end time in seconds

        Expected format:
        [
            {
                "youtube_url": "https://youtube.com/watch?v=xxx",
                "chamber": "house",
                "session_date": "2024-01-15",
                "sitting_number": "Sixty-Seventh Sitting",
                "order_paper_pdf": "path/to/paper.pdf"
            },
            ...
        ]
        """
        with open(mapping_file) as f:
            videos = json.load(f)

        logger.info(f"Found {len(videos)} videos to ingest")

        results = []
        for i, video_data in enumerate(videos, 1):
            logger.info(f"Processing {i}/{len(videos)}")

            # Load order paper if specified
            order_paper = None
            if "order_paper_pdf" in video_data:
                from parsers.order_paper_parser import OrderPaperParser

                parser = OrderPaperParser(self.client)
                order_paper = parser.parse(Path(video_data["order_paper_pdf"]))

            result = await self.ingest_video(
                youtube_url=video_data["youtube_url"],
                chamber=video_data.get("chamber", "house"),
                session_date=datetime.fromisoformat(video_data["session_date"])
                if video_data.get("session_date")
                else None,
                sitting_number=video_data.get("sitting_number"),
                order_paper=order_paper,
                fps=video_data.get("fps", fps),
                start_time=video_data.get("start_time", start_time),
                end_time=video_data.get("end_time", end_time),
            )
            results.append(result)

        return results

    async def _get_speaker_id_mapping(self) -> dict[str, str]:
        """Build mapping of speaker names to IDs"""
        result = await self.db.execute(select(Speaker))
        speakers = result.scalars().all()

        return {s.name: s.canonical_id for s in speakers}

    def _log_run_summary(self, youtube_id: str) -> None:
        usage_by_stage: dict[str, dict[str, float]] = {}
        usage_log = getattr(self.client, "usage_log", []) or []
        if not isinstance(usage_log, list):
            try:
                usage_log = list(usage_log)
            except TypeError:
                usage_log = []
        for usage in usage_log:
            stage = usage.get("stage", "unknown")
            entry = usage_by_stage.setdefault(
                stage,
                {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "duration_ms": 0.0,
                },
            )
            entry["calls"] += 1
            entry["prompt_tokens"] += usage.get("prompt_tokens", 0)
            entry["output_tokens"] += usage.get("output_tokens", 0)
            entry["total_tokens"] += usage.get("total_tokens", 0)
            entry["duration_ms"] += float(usage.get("duration_ms", 0.0))

        logger.info("Timing summary for %s (ms): %s", youtube_id, self.stage_timings_ms)
        logger.info("Token usage summary for %s: %s", youtube_id, usage_by_stage)

    async def _get_speaker_lookup(self) -> dict[str, Speaker]:
        result = await self.db.execute(select(Speaker))
        speakers = result.scalars().all()
        return {s.canonical_id: s for s in speakers if s.canonical_id}

    async def _persist_knowledge_graph(
        self,
        video: VideoModel,
        transcript: SessionTranscript,
        extraction,
        sentence_segment_map: dict[tuple[int, int, int], str],
    ) -> None:
        speaker_lookup = await self._get_speaker_lookup()

        entities = list(extraction.entities)
        relationships = list(extraction.relationships)

        speaker_entities = self._build_speaker_entities(
            transcript, speaker_lookup, video.youtube_id
        )
        agenda_entities = self._build_agenda_entities(video.youtube_id, transcript)
        entities = self._merge_entities(entities, speaker_entities + agenda_entities)

        mentions, agenda_entity_map, evidence_map = self._build_mentions(
            video,
            transcript,
            entities,
            sentence_segment_map,
        )
        self._apply_entity_evidence(entities, evidence_map)
        relationships.extend(
            self._build_agenda_relationships(
                transcript,
                agenda_entities=agenda_entities,
                agenda_entity_map=agenda_entity_map,
                video_id=video.youtube_id,
            )
        )

        await self._upsert_entities(entities)
        await self._replace_relationships(video, relationships)
        await self._replace_mentions(video, mentions)

    async def _upsert_entities(self, entities: list[Entity]) -> None:
        for entity in entities:
            result = await self.db.execute(
                select(Entity).where(Entity.entity_id == entity.entity_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                source_value: str
                if entity.source:
                    source_value = cast(str, entity.source)
                elif existing.source:
                    source_value = cast(str, existing.source)
                else:
                    source_value = "unknown"
                existing.entity_type = entity.entity_type
                existing.entity_subtype = entity.entity_subtype
                existing.name = entity.name
                existing.canonical_name = entity.canonical_name
                existing.aliases = entity.aliases or []
                existing.description = getattr(entity, "description", None)
                existing.importance_score = getattr(entity, "importance_score", 0.0)
                existing.entity_confidence = getattr(entity, "entity_confidence", None)
                existing.source = source_value
                existing.source_ref = getattr(entity, "source_ref", None)
                existing.speaker_canonical_id = getattr(entity, "speaker_canonical_id", None)
            else:
                source_value: str = cast(str, entity.source) if entity.source else "unknown"
                self.db.add(
                    Entity(
                        entity_id=entity.entity_id,
                        entity_type=entity.entity_type,
                        entity_subtype=entity.entity_subtype,
                        name=entity.name,
                        canonical_name=entity.canonical_name,
                        aliases=entity.aliases or [],
                        description=getattr(entity, "description", None),
                        importance_score=getattr(entity, "importance_score", 0.0),
                        entity_confidence=getattr(entity, "entity_confidence", None),
                        source=source_value,
                        source_ref=getattr(entity, "source_ref", None),
                        speaker_canonical_id=getattr(entity, "speaker_canonical_id", None),
                    )
                )

    async def _replace_relationships(
        self, video: VideoModel, relationships: list[Relationship]
    ) -> None:
        await self.db.execute(delete(Relationship).where(Relationship.video_id == video.id))
        for relationship in relationships:
            source_value: str = cast(str, relationship.source) if relationship.source else "unknown"
            self.db.add(
                Relationship(
                    source_id=relationship.source_id,
                    target_id=relationship.target_id,
                    relation_type=relationship.relation_type,
                    sentiment=relationship.sentiment,
                    evidence=relationship.evidence,
                    confidence=relationship.confidence,
                    source=source_value,
                    source_ref=relationship.source_ref,
                    video_id=video.id,
                    timestamp_seconds=relationship.timestamp_seconds,
                )
            )

    async def _replace_segments(
        self, video: VideoModel, segments: list[TranscriptSegmentData]
    ) -> None:
        await self.db.execute(
            delete(TranscriptSegment).where(TranscriptSegment.video_id == video.id)
        )
        if not segments:
            return

        embeddings = self.embedding_service.generate_embeddings(
            [segment.text for segment in segments]
        )
        for segment, embedding in zip(segments, embeddings, strict=True):
            self.db.add(
                TranscriptSegment(
                    video_id=video.id,
                    segment_id=segment.segment_id,
                    agenda_item_index=segment.agenda_item_index,
                    speech_block_index=segment.speech_block_index,
                    segment_index=segment.segment_index,
                    start_time_seconds=segment.start_time_seconds,
                    end_time_seconds=segment.end_time_seconds,
                    speaker_id=segment.speaker_id,
                    text=segment.text,
                    embedding=embedding,
                    embedding_model=self.embedding_service.model_name,
                    embedding_version=self.embedding_service.model_version,
                    meta_data={"sentence_indices": segment.sentence_indices},
                )
            )

    async def _replace_mentions(self, video: VideoModel, mentions: list[Mention]) -> None:
        await self.db.execute(delete(Mention).where(Mention.video_id == video.id))
        for mention in mentions:
            self.db.add(
                Mention(
                    entity_id=mention.entity_id,
                    video_id=video.id,
                    agenda_item_index=mention.agenda_item_index,
                    speech_block_index=mention.speech_block_index,
                    sentence_index=mention.sentence_index,
                    timestamp_seconds=mention.timestamp_seconds,
                    context=mention.context,
                    bill_id=mention.bill_id,
                    speaker_id=mention.speaker_id,
                    speaker_canonical_id=mention.speaker_canonical_id,
                    agenda_title=mention.agenda_title,
                    segment_id=mention.segment_id,
                )
            )

    def _build_speaker_entities(
        self,
        transcript: SessionTranscript,
        speaker_lookup: dict[str, Speaker],
        video_id: str,
    ) -> list[Entity]:
        speakers: dict[str, str] = {}
        for agenda in transcript.agenda_items:
            for speech in agenda.speech_blocks or []:
                if not speech.speaker_id:
                    continue
                speakers[speech.speaker_id] = speech.speaker_name

        entities: list[Entity] = []
        for speaker_id, speaker_name in speakers.items():
            speaker_record = speaker_lookup.get(speaker_id)
            role = speaker_record.role if speaker_record else None
            subtype = "speaker"
            if role and "minister" in role.lower():
                subtype = "minister"
            elif role and ("member" in role.lower() or "mp" in role.lower()):
                subtype = "mp"

            description = "Parliamentary speaker"
            if role:
                description = role

            entities.append(
                Entity(
                    entity_id=speaker_id,
                    entity_type="person",
                    entity_subtype=subtype,
                    name=speaker_name,
                    canonical_name=speaker_name,
                    aliases=[],
                    description=description,
                    importance_score=1.0,
                    entity_confidence=1.0,
                    source="order_paper" if speaker_record else "transcript",
                    source_ref=video_id,
                    speaker_canonical_id=speaker_id,
                )
            )
        return entities

    def _build_agenda_entities(self, video_id: str, transcript: SessionTranscript) -> list[Entity]:
        entities: list[Entity] = []
        for index, agenda in enumerate(transcript.agenda_items):
            entity_id = f"agenda-{video_id}-{index}"
            entities.append(
                Entity(
                    entity_id=entity_id,
                    entity_type="agenda_item",
                    entity_subtype="agenda_item",
                    name=agenda.topic_title,
                    canonical_name=agenda.topic_title,
                    aliases=[],
                    description=None,
                    importance_score=1.0,
                    entity_confidence=1.0,
                    source="transcript",
                    source_ref=video_id,
                )
            )
        return entities

    def _build_mentions(
        self,
        video: VideoModel,
        transcript: SessionTranscript,
        entities: list[Entity],
        sentence_segment_map: dict[tuple[int, int, int], str],
    ) -> tuple[list[Mention], dict[int, set[str]], dict[str, dict[str, list]]]:
        import re
        from thefuzz import fuzz

        mentions: list[Mention] = []
        agenda_entity_map: dict[int, set[str]] = {}
        evidence_map: dict[str, dict[str, list]] = {}

        search_entities = [
            entity for entity in entities if entity.entity_type not in {"agenda_item"}
        ]

        for agenda_idx, agenda in enumerate(transcript.agenda_items):
            for block_idx, speech in enumerate(agenda.speech_blocks or []):
                sentences = speech.sentences or []
                for sentence_idx, sentence in enumerate(sentences):
                    sentence_text = sentence.text
                    sentence_lower = sentence_text.lower()
                    timestamp = self._parse_timecode(sentence.start_time)
                    segment_id = sentence_segment_map.get((agenda_idx, block_idx, sentence_idx))

                    for entity in search_entities:
                        if (
                            entity.entity_subtype == "speaker"
                            and entity.entity_id == speech.speaker_id
                        ):
                            continue

                        variants = [entity.name] + (entity.aliases or [])
                        if not any(isinstance(v, str) for v in variants):
                            continue

                        matched = False
                        for variant in variants:
                            if not isinstance(variant, str) or not variant.strip():
                                continue
                            pattern = re.compile(r"\b" + re.escape(variant.lower()) + r"\b")
                            if pattern.search(sentence_lower):
                                matched = True
                                break
                            if fuzz.partial_ratio(variant.lower(), sentence_lower) >= 80:
                                matched = True
                                break

                        if not matched:
                            continue

                        mentions.append(
                            Mention(
                                entity_id=entity.entity_id,
                                video_id=video.id,
                                agenda_item_index=agenda_idx,
                                speech_block_index=block_idx,
                                sentence_index=sentence_idx,
                                timestamp_seconds=timestamp,
                                context=sentence_text,
                                bill_id=agenda.bill_id,
                                speaker_id=speech.speaker_id,
                                speaker_canonical_id=speech.speaker_id,
                                agenda_title=agenda.topic_title,
                                segment_id=segment_id,
                            )
                        )
                        agenda_entity_map.setdefault(agenda_idx, set()).add(entity.entity_id)

                        if segment_id:
                            evidence = evidence_map.setdefault(
                                entity.entity_id,
                                {"segment_ids": [], "timestamps": [], "evidence": []},
                            )
                            evidence["segment_ids"].append(segment_id)
                            if timestamp is not None:
                                evidence["timestamps"].append(timestamp)
                            evidence["evidence"].append(sentence_text)

        return mentions, agenda_entity_map, evidence_map

    def _apply_entity_evidence(
        self, entities: list[Entity], evidence_map: dict[str, dict[str, list]]
    ) -> None:
        for entity in entities:
            evidence = evidence_map.get(entity.entity_id)
            if not evidence:
                continue
            meta_data = dict(entity.meta_data or {})
            meta_data["segment_ids"] = list(dict.fromkeys(evidence["segment_ids"]))
            meta_data["timestamps"] = list(dict.fromkeys(evidence["timestamps"]))
            meta_data["evidence"] = evidence["evidence"]
            entity.meta_data = meta_data

    def _build_agenda_relationships(
        self,
        transcript: SessionTranscript,
        agenda_entities: list[Entity],
        agenda_entity_map: dict[int, set[str]],
        video_id: str,
    ) -> list[Relationship]:
        relationships: list[Relationship] = []
        agenda_lookup = {idx: entity for idx, entity in enumerate(agenda_entities)}

        for agenda_idx, agenda in enumerate(transcript.agenda_items):
            agenda_entity = agenda_lookup.get(agenda_idx)
            if not agenda_entity:
                continue
            speakers = []
            for speech in agenda.speech_blocks or []:
                if speech.speaker_id:
                    speakers.append(speech)

            for speech in speakers:
                timestamp = None
                if speech.sentences:
                    timestamp = self._parse_timecode(speech.sentences[0].start_time)
                relationships.append(
                    Relationship(
                        source_id=speech.speaker_id,
                        target_id=agenda_entity.entity_id,
                        relation_type="speaks_on",
                        sentiment=None,
                        evidence=f"Spoke during agenda item: {agenda.topic_title}",
                        confidence=1.0,
                        source="derived",
                        source_ref=video_id,
                        timestamp_seconds=timestamp,
                    )
                )

            for entity_id in agenda_entity_map.get(agenda_idx, set()):
                relationships.append(
                    Relationship(
                        source_id=agenda_entity.entity_id,
                        target_id=entity_id,
                        relation_type="about",
                        sentiment=None,
                        evidence=f"Mentioned during agenda item: {agenda.topic_title}",
                        confidence=1.0,
                        source="derived",
                        source_ref=video_id,
                        timestamp_seconds=None,
                    )
                )

        return relationships

    def _segment_transcript(
        self,
        transcript: SessionTranscript,
        speaker_lookup: dict[str, Speaker],
    ) -> tuple[list[TranscriptSegmentData], dict[tuple[int, int, int], str]]:
        segmenter = TranscriptSegmenter()
        segments = segmenter.segment(transcript)
        sentence_segment_map: dict[tuple[int, int, int], str] = {}
        updated_segments: list[TranscriptSegmentData] = []
        for segment in segments:
            speaker_id = segment.speaker_id
            if speaker_id and speaker_id not in speaker_lookup:
                speaker_id = None
            updated_segments.append(
                TranscriptSegmentData(
                    segment_id=segment.segment_id,
                    agenda_item_index=segment.agenda_item_index,
                    speech_block_index=segment.speech_block_index,
                    segment_index=segment.segment_index,
                    speaker_id=speaker_id,
                    start_time_seconds=segment.start_time_seconds,
                    end_time_seconds=segment.end_time_seconds,
                    text=segment.text,
                    sentence_indices=segment.sentence_indices,
                )
            )
            for sentence_idx in segment.sentence_indices:
                sentence_segment_map[
                    (
                        segment.agenda_item_index,
                        segment.speech_block_index,
                        sentence_idx,
                    )
                ] = segment.segment_id
        return updated_segments, sentence_segment_map

    def _merge_entities(self, entities: list[Entity], additions: list[Entity]) -> list[Entity]:
        existing_ids = {entity.entity_id for entity in entities}
        for entity in additions:
            if entity.entity_id not in existing_ids:
                entities.append(entity)
                existing_ids.add(entity.entity_id)
        return entities

    def _parse_timecode(self, time_str: str) -> int | None:
        import re

        match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
        if not match:
            return None
        minutes, seconds, ms = map(int, match.groups())
        return minutes * 60 + seconds

    def _extract_youtube_id(self, url: str) -> str:
        """Extract YouTube ID from URL"""
        pattern = r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)"
        import re

        match = re.search(pattern, url)
        if not match:
            raise ValueError(f"Invalid YouTube URL: {url}")
        return match.group(1)

    def _parse_simple_response(self, response: dict) -> SessionTranscript:
        """Parse Gemini response without order paper"""
        return self.transcription_service._parse_response(response)

    def _serialize_transcript(self, transcript: Any) -> dict[str, Any]:
        """Serialize transcript payload into JSON-safe dict."""
        payload = cast(Any, transcript)
        model_dump = getattr(payload, "model_dump", None)
        if callable(model_dump):
            return cast(dict[str, Any], model_dump())
        if is_dataclass(transcript) and not isinstance(transcript, type):
            return cast(dict[str, Any], self._normalize_json(asdict(cast(Any, transcript))))
        if isinstance(transcript, dict):
            return cast(dict[str, Any], self._normalize_json(transcript))
        return {}

    def _normalize_json(self, payload: Any) -> Any:
        """Normalize payload for JSON storage."""
        if isinstance(payload, datetime):
            return payload.isoformat()
        if isinstance(payload, date):
            return payload.isoformat()
        if isinstance(payload, list):
            return [self._normalize_json(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._normalize_json(value) for key, value in payload.items()}
        return payload


async def main():
    parser = argparse.ArgumentParser(description="Ingest videos to database")
    parser.add_argument(
        "--url",
        help="YouTube URL to ingest",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        help="JSON file with video metadata",
    )
    parser.add_argument(
        "--chamber",
        choices=["house", "senate"],
        default="house",
        help="Chamber (default: house)",
    )
    parser.add_argument(
        "--session-date",
        help="Session date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--sitting-number",
        help="Sitting number",
    )
    parser.add_argument(
        "--fps",
        type=float,
        help="Frames per second for video sampling",
    )
    parser.add_argument(
        "--start-time",
        type=int,
        help="Start time in seconds",
    )
    parser.add_argument(
        "--end-time",
        type=int,
        help="End time in seconds",
    )
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable thinking budget for Gemini",
    )
    parser.add_argument(
        "--order-paper",
        type=Path,
        help="Path to order paper PDF for context",
    )

    args = parser.parse_args()

    settings = get_settings()

    thinking_budget = 0 if args.no_thinking else None
    client = GeminiClient(
        api_key=settings.google_api_key,
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        thinking_budget=thinking_budget,
    )

    async with _db_session() as db:
        ingestor = VideoIngestor(
            db,
            client,
            entity_extractor=EntityExtractor(
                api_key=settings.google_api_key,
                thinking_budget=thinking_budget,
            ),
        )

        if args.mapping:
            results = await ingestor.ingest_from_file(
                args.mapping,
                fps=args.fps,
                start_time=args.start_time,
                end_time=args.end_time,
            )

            success = sum(1 for r in results if r["status"] == "success")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            failed = sum(1 for r in results if r["status"] == "error")

            print("\nResults:")
            print(f"  Success: {success}")
            print(f"  Skipped: {skipped}")
            print(f"  Failed: {failed}")
        elif args.url:
            order_paper = None
            if args.order_paper:
                from parsers.order_paper_parser import OrderPaperParser

                parser = OrderPaperParser(client)
                parse_start = time.perf_counter()
                order_paper = parser.parse(args.order_paper)
                ingestor.stage_timings_ms["order_paper_parse"] = (
                    time.perf_counter() - parse_start
                ) * 1000
            result = await ingestor.ingest_video(
                youtube_url=args.url,
                chamber=args.chamber,
                session_date=datetime.fromisoformat(args.session_date)
                if args.session_date
                else None,
                sitting_number=args.sitting_number,
                order_paper=order_paper,
                fps=args.fps,
                start_time=args.start_time,
                end_time=args.end_time,
            )
            print(result)
        else:
            parser.print_help()


@asynccontextmanager
async def _db_session() -> AsyncIterator[AsyncSession]:
    """Provide an async session from the app dependency."""
    async for session in get_db_session():
        yield session


if __name__ == "__main__":
    asyncio.run(main())
