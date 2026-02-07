#!/usr/bin/env python3
"""Ingest videos to database with transcription and knowledge graph extraction"""

import argparse
import asyncio
import json
import logging
import random
import re
import sys
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from core.database import get_session_maker
from models.agenda_item import AgendaItem
from models.entity import Entity
from models.relationship import Relationship
from models.relationship_evidence import RelationshipEvidence
from models.session import Session as SessionModel
from models.speaker import Speaker
from models.transcript_segment import TranscriptSegment
from models.video import Video
from parsers.transcript_models import SessionTranscript, parse_gemini_transcript_response
from services.embeddings import EmbeddingService
from services.entity_extractor import EntityExtractor, ExtractedRelationship, ExtractionResult
from services.gemini import GeminiClient
from services.transcript_segmenter import TranscriptSegmentData, TranscriptSegmenter
from services.video_transcription import VideoTranscriptionService


class VideoMetadata(BaseModel):
    """Extracted video metadata from LLM."""

    session_date: date | None = Field(
        None, description="Session date in YYYY-MM-DD format if found"
    )
    chamber: str | None = Field(None, description="Chamber: 'house' or 'senate' if identifiable")
    title: str | None = Field(None, description="Session title if found")
    sitting_number: str | None = Field(None, description="Sitting number if found")


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VideoIngestor:
    """Ingests videos into database with new schema"""

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
        self.embedding_service = embedding_service or EmbeddingService(
            gemini_client=None
        )  # Use local sentence-transformers for embeddings
        self.stage_timings_ms: dict[str, float] = {}

    async def ingest_video(
        self,
        youtube_url: str,
        chamber: str = "house",
        session_date: date | None = None,
        sitting_number: str | None = None,
        session_id: str | None = None,
        fps: float | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict[str, object]:
        """
        Transcribe and save a video with knowledge graph extraction.

        Args:
            youtube_url: YouTube URL
            chamber: 'house' or 'senate'
            session_date: Session date
            sitting_number: Sitting number
            session_id: Stable session ID (generated if not provided)
            fps: Frames per second for video sampling

        Returns:
            Dictionary with ingest status and IDs
        """
        overall_start = time.perf_counter()
        youtube_id = self._extract_youtube_id(youtube_url)

        logger.info("Ingesting video: %s", youtube_id)

        existing = await self.db.execute(select(Video).where(Video.video_id == youtube_id))
        if existing.scalar_one_or_none():
            logger.info("Video already exists: %s", youtube_id)
            return {"status": "skipped", "reason": "already_exists"}

        existing_segments = await self.db.execute(
            select(TranscriptSegment).where(TranscriptSegment.video_id == youtube_id)
        )
        if existing_segments.scalar_one_or_none():
            logger.info("Segments already exist for video: %s", youtube_id)
            return {"status": "skipped", "reason": "segments_already_exist"}

        try:
            if not session_date:
                detected_date, detected_chamber, detected_title, detected_sitting = (
                    self._auto_detect_session_date(youtube_url)
                )
                if detected_date:
                    session_date = detected_date
                    logger.info("Auto-determined session_date: %s", session_date)
                if not chamber and detected_chamber:
                    chamber = detected_chamber
                    logger.info("Auto-determined chamber: %s", chamber)
                if detected_sitting and not sitting_number:
                    sitting_number = detected_sitting
                    logger.info("Auto-determined sitting_number: %s", sitting_number)

            session_id = await self._ensure_session_id(
                chamber, session_date, sitting_number, session_id
            )
            transcript = await self._transcribe_video(
                youtube_url,
                fps,
                start_time,
                end_time,
            )
            extraction, entities_count = self._extract_knowledge_graph(transcript, session_id)
            video = await self._persist_all_data(
                youtube_url,
                youtube_id,
                session_id,
                chamber,
                session_date,
                sitting_number,
                transcript,
                extraction,
            )

            self.stage_timings_ms["total"] = (time.perf_counter() - overall_start) * 1000
            self._log_run_summary(youtube_id)

            return self._build_success_result(video.video_id, session_id, entities_count)

        except (
            ValueError,
            KeyError,
            json.JSONDecodeError,
            AttributeError,
            IndexError,
            TypeError,
        ) as e:
            logger.error("Failed to ingest video: %s", e, exc_info=True)
            await self.db.rollback()
            return {"status": "error", "error": str(e)}

    async def _video_exists(self, youtube_id: str) -> bool:
        """Check if a video already exists in the database."""
        existing = await self.db.execute(select(Video).where(Video.video_id == youtube_id))
        return existing.scalar_one_or_none() is not None

    async def _ensure_session_id(
        self,
        chamber: str,
        session_date: date | None,
        sitting_number: str | None,
        session_id: str | None,
    ) -> str:
        """Find existing session or generate new session ID."""
        if session_id:
            return session_id

        # Try to find existing session by date and chamber
        if session_date:
            existing_session = await self._find_existing_session(chamber, session_date)
            if existing_session:
                logger.info("Found existing session: %s", existing_session)
                return existing_session

        # Generate new session ID if no existing session found
        generated = self._generate_session_id(chamber, session_date, sitting_number)
        logger.info("Generated new session_id: %s", generated)
        return generated

    async def _find_existing_session(self, chamber: str, session_date: date) -> str | None:
        """Find an existing session by chamber and date."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.chamber == chamber, SessionModel.date == session_date
            )
        )
        session = result.scalar_one_or_none()
        return session.session_id if session else None

    def _auto_detect_session_date(
        self, youtube_url: str
    ) -> tuple[date | None, str | None, str | None, str | None]:
        """Extract session date, chamber, title, sitting number from video metadata using LLM."""
        video_id = self._extract_video_id(youtube_url)
        if not video_id:
            return None, None, None, None

        methods_to_try = [
            ("Invidious", lambda: self._get_from_invidious(video_id)),
            ("Piped", lambda: self._get_from_piped(video_id)),
            ("oEmbed", lambda: self._get_from_oembed(video_id)),
            ("RSS Feed", lambda: self._get_from_rss(video_id)),
            ("YouTube Watch Page", lambda: self._get_from_watch_page(video_id)),
        ]

        for method_name, method_func in methods_to_try:
            try:
                logger.info("Trying %s method...", method_name)
                title, description, upload_date = method_func()

                if title and title != "Unknown":
                    logger.info("✓ %s succeeded! Title: %s", method_name, title)
                    if upload_date:
                        logger.info("  Upload date: %s", upload_date)

                    metadata = self._extract_metadata_with_llm(title, description, upload_date)

                    if metadata.session_date:
                        logger.info("Extracted session_date: %s", metadata.session_date)
                    if metadata.chamber:
                        logger.info("Extracted chamber: %s", metadata.chamber)
                    if metadata.title:
                        logger.info("Extracted title: %s", metadata.title)

                    return (
                        metadata.session_date,
                        metadata.chamber,
                        metadata.title,
                        metadata.sitting_number,
                    )
                else:
                    logger.warning("✗ %s method failed - no title found", method_name)

            except Exception as e:
                logger.warning("✗ %s method failed: %s", method_name, str(e)[:100])
                continue

        logger.warning("All methods failed, falling back to current date")
        return None, None, None, None

    def _get_user_agent(self) -> str:
        """Get a random user agent to rotate requests."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        return random.choice(user_agents)

    def _get_from_invidious(self, video_id: str) -> tuple[str, str, str]:
        """Fetch metadata from Invidious instance."""
        invidious_instances = [
            "https://inv.tux.pizza",
            "https://invidious.snopyta.org",
            "https://yewtu.be",
            "https://invidious.fdn.fr",
        ]

        for instance in invidious_instances:
            try:
                url = f"{instance}/api/v1/videos/{video_id}"
                headers = {"User-Agent": self._get_user_agent()}
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    title = data.get("title", "")
                    description = data.get("description", "") or "N/A"
                    upload_date_raw = data.get("uploadDate")

                    upload_date = ""
                    if upload_date_raw:
                        dt = datetime.fromisoformat(upload_date_raw.replace("Z", "+00:00"))
                        upload_date = dt.strftime("%Y%m%d")

                    return title, description, upload_date
            except Exception:
                continue

        return "Unknown", "N/A", ""

    def _get_from_piped(self, video_id: str) -> tuple[str, str, str]:
        """Fetch metadata from Piped instance."""
        piped_instances = [
            "https://pipedapi.kavin.rocks",
            "https://piped-api.garudalinux.org",
        ]

        for instance in piped_instances:
            try:
                url = f"{instance}/videos/{video_id}"
                headers = {"User-Agent": self._get_user_agent()}
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    title = data.get("title", "")
                    description = data.get("description", "") or "N/A"
                    upload_date_raw = data.get("uploadedDate")

                    upload_date = ""
                    if upload_date_raw:
                        dt = datetime.fromisoformat(upload_date_raw.replace("Z", "+00:00"))
                        upload_date = dt.strftime("%Y%m%d")

                    return title, description, upload_date
            except Exception:
                continue

        return "Unknown", "N/A", ""

    def _get_from_oembed(self, video_id: str) -> tuple[str, str, str]:
        """Fetch metadata from YouTube oEmbed endpoint."""
        try:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            headers = {"User-Agent": self._get_user_agent()}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                title = data.get("title", "")
                return title, "N/A", ""
        except Exception:
            pass
        return "Unknown", "N/A", ""

    def _get_from_rss(self, video_id: str) -> tuple[str, str, str]:
        """Fetch metadata from YouTube RSS feed."""
        try:
            url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}"
            headers = {"User-Agent": self._get_user_agent()}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                author_url = data.get("author_url", "")
                if author_url and "/@" in author_url:
                    channel_id = author_url.split("/@")[-1]
                    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                    rss_response = requests.get(
                        rss_url, headers={"User-Agent": self._get_user_agent()}, timeout=10
                    )
                    if rss_response.status_code == 200:
                        match = re.search(
                            r"<title><!\[CDATA\[([^\]]+)\]\]></title>", rss_response.text
                        )
                        if match:
                            return match.group(1), "N/A", ""
        except Exception:
            pass
        return "Unknown", "N/A", ""

    def _get_from_watch_page(self, video_id: str) -> tuple[str, str, str]:
        """Fetch metadata from YouTube watch page with rotated user agents."""
        url = f"https://www.youtube.com/watch?v={video_id}"

        for attempt in range(3):
            try:
                headers = {"User-Agent": self._get_user_agent()}
                response = requests.get(url, headers=headers, timeout=5)
                response.raise_for_status()
                html = response.text

                title = "Unknown"
                description = "N/A"
                upload_date = ""

                match = re.search(r"<title>([^<]+)</title>", html)
                if match:
                    title = unescape(match.group(1)).replace(" - YouTube", "").strip()

                match = re.search(r'"shortDescription"\s*:\s*"((?:\\"|[^"])*)"', html)
                if match:
                    desc_str = match.group(1)
                    description = unescape(desc_str.replace('\\"', '"')) or "N/A"

                match = re.search(r'"uploadDate"\s*:\s*"([^"]+)"', html)
                if match:
                    upload_date = match.group(1)
                else:
                    match = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
                    if match:
                        upload_date = match.group(1)

                if title and title != "Unknown":
                    return title, description, upload_date

            except Exception:
                if attempt < 2:
                    time.sleep(1)
                    continue

        return "Unknown", "N/A", ""

    def _extract_video_id(self, youtube_url: str) -> str | None:
        """Extract video ID from YouTube URL."""
        patterns = [
            r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})',
            r'youtube\.com\/shorts\/([^"&?\/\s]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        return None

    def _get_video_info_from_page(self, video_id: str) -> tuple[str, str, str]:
        """Fetch video metadata from public YouTube watch page (no auth required)."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text

        title = "Unknown"
        description = "N/A"
        upload_date = ""

        match = re.search(r'"title"\s*:\s*"((?:\\"|[^"])*)"', html)
        if match:
            title_str = match.group(1)
            title = unescape(title_str.replace('\\"', '"'))

        match = re.search(r'"shortDescription"\s*:\s*"((?:\\"|[^"])*)"', html)
        if match:
            desc_str = match.group(1)
            description = unescape(desc_str.replace('\\"', '"')) or "N/A"

        match = re.search(r'"uploadDate"\s*:\s*"([^"]+)"', html)
        if match:
            upload_date = match.group(1)
        else:
            match = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
            if match:
                upload_date = match.group(1)

        return title, description, upload_date

    def _extract_metadata_with_llm(
        self,
        title: str | None,
        description: str,
        upload_date: str,
    ) -> VideoMetadata:
        """Use LLM to extract session metadata from video metadata."""
        if not description:
            description = "N/A"
        if not title:
            title = "Unknown"

        prompt = f"""Extract parliamentary session information from this YouTube video metadata.

Video Title: {title}
Upload Date: {upload_date}
Description: {description[:2000]}

Extract the following information:
- session_date: The session date in YYYY-MM-DD format (look for dates in title, description)
- chamber: "house" or "senate" (look for keywords like "House of Assembly", "Senate")
- title: A brief title for the session
- sitting_number: The sitting number if mentioned (e.g., "10th", "Sitting 10")

Return null for any field that cannot be confidently determined."""

        response_schema = VideoMetadata.model_json_schema()
        response_data = self.client.generate_structured(
            prompt=prompt,
            response_schema=response_schema,
            stage="metadata_extraction",
        )

        return VideoMetadata(**response_data)

    async def _transcribe_video(
        self,
        youtube_url: str,
        fps: float | None,
        start_time: int | None,
        end_time: int | None,
    ) -> SessionTranscript:
        """Transcribe a YouTube video into a structured transcript."""
        effective_fps = fps if fps is not None else 0.25

        transcript_start = time.perf_counter()
        prompt = """Transcribe this Barbados parliamentary session.

STRUCTURE:
1. Group by agenda items naturally
2. For each speech block:
   - speaker_name: Name as spoken
   - sentences: List of sentences with timestamps

TIMESTAMP FORMAT - CRITICAL REQUIREMENT:
ALL timestamps MUST use this EXACT format: XmYsZms (minutes, seconds, milliseconds)
- Examples: 0m0s0ms, 2m34s500ms, 45m10s100ms
- NEVER use: "0:00", "00:00:00", PT0S, or any other format
- Each sentence MUST have a timestamp

INSTRUCTIONS:
- Preserve parliamentary language and formal tone
- Identify speaker changes clearly
- Include all content
- ENSURE CORRECT TIMESTAMP FORMAT FOR EVERY SENTENCE"""

        print("\n" + "=" * 80)
        print("TRANSCRIPTION PROMPT:")
        print("=" * 80)
        print(prompt)
        print("=" * 80 + "\n")

        response = self.client.analyze_video_with_transcript(
            video_url=youtube_url,
            prompt=prompt,
            response_schema=VideoTranscriptionService.TRANSCRIPT_SCHEMA,
            fps=effective_fps,
            start_time=start_time,
            end_time=end_time,
        )

        transcript = self.transcription_service._parse_response(response)
        self.stage_timings_ms["transcription"] = (time.perf_counter() - transcript_start) * 1000

        if not transcript:
            raise ValueError("empty_transcript")

        return transcript

    def _extract_knowledge_graph(
        self,
        transcript: SessionTranscript,
        session_id: str,
    ) -> tuple[ExtractionResult, int]:
        """Extract entities and relationships from transcript."""
        if not self.entity_extractor:
            return ExtractionResult(session_id=session_id, entities=[], relationships=[]), 0

        extract_start = time.perf_counter()
        extraction = self.entity_extractor.extract_from_transcript(transcript)
        self.stage_timings_ms["kg_extraction"] = (time.perf_counter() - extract_start) * 1000
        return extraction, len(extraction.entities)

    async def _persist_all_data(
        self,
        youtube_url: str,
        youtube_id: str,
        session_id: str,
        chamber: str,
        session_date: date | None,
        sitting_number: str | None,
        transcript: SessionTranscript,
        extraction: ExtractionResult,
    ) -> Video:
        """Persist session, video, transcript, and knowledge graph data."""
        await self._persist_session_and_video(
            youtube_url,
            youtube_id,
            session_id,
            chamber,
            session_date,
            sitting_number,
        )

        video = await self._fetch_video(youtube_id)

        await self._persist_speakers(transcript)
        await self._persist_agenda_items(session_id, transcript)
        segment_id_lookup = await self._persist_transcript_segments(
            video, youtube_id, session_id, transcript
        )

        if extraction.entities or extraction.relationships:
            await self._persist_knowledge_graph(
                video, session_id, youtube_id, transcript, extraction, segment_id_lookup
            )

        await self.db.commit()
        await self.db.refresh(video)

        return video

    async def _fetch_video(self, youtube_id: str) -> Video:
        """Fetch a persisted video or raise if missing."""
        result = await self.db.execute(select(Video).where(Video.video_id == youtube_id))
        try:
            return result.scalar_one()
        except NoResultFound as exc:
            raise ValueError(f"Video {youtube_id} not found after persistence") from exc

    def _build_success_result(
        self, video_id: str, session_id: str, entities_count: int
    ) -> dict[str, object]:
        """Build response payload for successful ingestion."""
        return {
            "status": "success",
            "video_id": video_id,
            "session_id": session_id,
            "entities_count": entities_count,
        }

    async def _persist_session_and_video(
        self,
        youtube_url: str,
        youtube_id: str,
        session_id: str,
        chamber: str,
        session_date: date | None,
        sitting_number: str | None,
    ) -> None:
        existing = await self.db.execute(
            select(SessionModel).where(SessionModel.session_id == session_id)
        )
        if not existing.scalar_one_or_none():
            session = SessionModel(
                session_id=session_id,
                date=session_date or datetime.now(timezone.utc).date(),
                title=f"{chamber.title()} Parliamentary Session",
                sitting_number=sitting_number or "0",
                chamber=chamber,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self.db.add(session)

        existing_video = await self.db.execute(select(Video).where(Video.video_id == youtube_id))
        if not existing_video.scalar_one_or_none():
            video = Video(
                video_id=youtube_id,
                session_id=session_id,
                platform="youtube",
                url=youtube_url,
                duration_seconds=None,
            )
            self.db.add(video)

    async def _persist_speakers(self, transcript: SessionTranscript) -> None:
        speaker_set = set()
        for agenda in transcript.agenda_items:
            for speech in agenda.speech_blocks or []:
                if speech.speaker_name:
                    if speech.speaker_id:
                        speaker_set.add((speech.speaker_id, speech.speaker_name))
                    else:
                        speaker_id = self._generate_speaker_id(speech.speaker_name)
                        speaker_set.add((speaker_id, speech.speaker_name))

        for canonical_id, name in speaker_set:
            existing = await self.db.execute(
                select(Speaker).where(Speaker.canonical_id == canonical_id)
            )
            if not existing.scalar_one_or_none():
                self.db.add(
                    Speaker(
                        canonical_id=canonical_id,
                        name=name,
                        title=None,
                        role=None,
                        chamber=None,
                        aliases=[],
                    )
                )

    async def _persist_agenda_items(self, session_id: str, transcript: SessionTranscript) -> None:
        for idx, agenda in enumerate(transcript.agenda_items):
            agenda_item_id = f"{session_id}_a{idx}"
            existing = await self.db.execute(
                select(AgendaItem).where(AgendaItem.agenda_item_id == agenda_item_id)
            )
            if not existing.scalar_one_or_none():
                self.db.add(
                    AgendaItem(
                        agenda_item_id=agenda_item_id,
                        session_id=session_id,
                        agenda_index=idx,
                        title=agenda.topic_title,
                        description=None,
                        primary_speaker=None,
                    )
                )

    async def _persist_transcript_segments(
        self,
        video: Video,
        youtube_id: str,
        session_id: str,
        transcript: SessionTranscript,
    ) -> dict[tuple[int, int, int], str]:
        await self.db.execute(
            delete(TranscriptSegment).where(TranscriptSegment.video_id == youtube_id)
        )
        await self.db.flush()

        segmenter = TranscriptSegmenter()
        segments = segmenter.segment(transcript)

        texts = [segment.text for segment in segments]
        embeddings = self.embedding_service.generate_embeddings(texts)

        segment_counter = 0
        used_segment_ids = set()

        for segment, embedding in zip(segments, embeddings, strict=True):
            start_time_seconds = segment.start_time_seconds or 0
            end_time_seconds = segment.end_time_seconds or (start_time_seconds + 10)

            base_id = f"{youtube_id}_{start_time_seconds:05d}"
            segment_id = base_id
            if segment_id in used_segment_ids:
                segment_counter += 1
                segment_id = f"{base_id}_c{segment_counter:02d}"

            used_segment_ids.add(segment_id)

            agenda_item_id = None
            if segment.agenda_item_index is not None:
                agenda_item_id = f"{session_id}_a{segment.agenda_item_index}"

            self.db.add(
                TranscriptSegment(
                    segment_id=segment_id,
                    session_id=session_id,
                    video_id=youtube_id,
                    speaker_id=segment.speaker_id,
                    start_time_seconds=start_time_seconds,
                    end_time_seconds=end_time_seconds,
                    text=segment.text,
                    agenda_item_id=agenda_item_id,
                    speech_block_index=segment.speech_block_index,
                    segment_index=segment.segment_index,
                    embedding=embedding,
                    embedding_model=self.embedding_service.model_name,
                )
            )

        return self._build_segment_id_lookup(segments, youtube_id)

    async def _persist_knowledge_graph(
        self,
        video: Video,
        session_id: str,
        youtube_id: str,
        transcript: SessionTranscript,
        extraction: ExtractionResult,
        segment_id_lookup: dict[tuple[int, int, int], str],
    ) -> None:
        entities = list(extraction.entities)
        relationships = list(extraction.relationships)

        await self._upsert_entities(entities)

        # Create entity name lookup for evidence matching
        entity_name_lookup = {entity.entity_id: entity.canonical_name for entity in entities}

        await self._replace_relationships_and_evidence(
            video,
            session_id,
            youtube_id,
            transcript,
            relationships,
            segment_id_lookup,
            entity_name_lookup,
        )

    async def _upsert_entities(self, entities: list[Entity]) -> None:
        for entity in entities:
            existing = await self.db.execute(
                select(Entity).where(Entity.entity_id == entity.entity_id)
            )
            if not existing.scalar_one_or_none():
                importance_score = getattr(entity, "importance_score", 0.0)
                entity_confidence = getattr(entity, "entity_confidence", None)
                source = getattr(entity, "source", "llm")
                source_ref = getattr(entity, "source_ref", None)
                self.db.add(
                    Entity(
                        entity_id=entity.entity_id,
                        name=entity.name,
                        canonical_name=entity.canonical_name,
                        entity_type=entity.entity_type,
                        entity_subtype=entity.entity_subtype,
                        description=entity.description,
                        aliases=entity.aliases or [],
                        importance_score=importance_score,
                        entity_confidence=entity_confidence,
                        source=source,
                        source_ref=source_ref,
                    )
                )

    async def _replace_relationships_and_evidence(
        self,
        video: Video,
        session_id: str,
        youtube_id: str,
        transcript: SessionTranscript,
        relationships: list[ExtractedRelationship],
        segment_id_lookup: dict[tuple[int, int, int], str],
        entity_name_lookup: dict[str, str],
    ) -> None:
        await self.db.execute(
            delete(RelationshipEvidence).where(RelationshipEvidence.video_id == youtube_id)
        )
        await self.db.execute(delete(Relationship).where(Relationship.source_ref == session_id))

        for rel in relationships:
            relationship_id = uuid.uuid4()
            self.db.add(
                Relationship(
                    relationship_id=relationship_id,
                    source_entity_id=rel.source_id,
                    target_entity_id=rel.target_id,
                    relation=rel.relation_type,
                    description=rel.evidence[:500],
                    sentiment=getattr(rel, "sentiment", None),
                    source=getattr(rel, "source", "llm"),
                    source_ref=getattr(rel, "source_ref", session_id),
                    confidence=rel.confidence or 1.0,
                )
            )

            segment_ids = self._find_segments_for_relationship(
                transcript, rel, segment_id_lookup, entity_name_lookup
            )

            if not segment_ids:
                continue

            result = await self.db.execute(
                select(TranscriptSegment).where(TranscriptSegment.segment_id.in_(segment_ids))
            )
            segments_by_id = {segment.segment_id: segment for segment in result.scalars().all()}

            for segment_id in segment_ids:
                segment = segments_by_id.get(segment_id)
                if not segment:
                    continue
                self.db.add(
                    RelationshipEvidence(
                        evidence_id=uuid.uuid4(),
                        relationship_id=relationship_id,
                        segment_id=segment_id,
                        video_id=youtube_id,
                        start_time_seconds=segment.start_time_seconds or 0,
                    )
                )

    def _build_segment_id_lookup(
        self, segments: list[TranscriptSegmentData], youtube_id: str
    ) -> dict[tuple[int, int, int], str]:
        """Build lookup from sentence indices to segment IDs."""
        result = {}
        for segment in segments:
            if not segment.sentence_indices:
                continue
            start_time_seconds = segment.start_time_seconds or 0
            segment_id = f"{youtube_id}_{start_time_seconds:05d}"
            for idx in segment.sentence_indices:
                result[(segment.agenda_item_index, segment.speech_block_index, idx)] = segment_id
        return result

    def _find_segments_for_relationship(
        self,
        transcript: SessionTranscript,
        relationship: ExtractedRelationship,
        segment_id_lookup: dict[tuple[int, int, int], str],
        entity_name_lookup: dict[str, str],
    ) -> list[str]:
        """Find segments containing relationship evidence."""
        segment_ids = set()
        relationship_text = (relationship.evidence or "").lower()
        source_name = entity_name_lookup.get(relationship.source_id, "").lower()
        target_name = entity_name_lookup.get(relationship.target_id, "").lower()

        for agenda_idx, agenda in enumerate(transcript.agenda_items):
            for block_idx, speech in enumerate(agenda.speech_blocks or []):
                for sentence_idx, sentence in enumerate(speech.sentences or []):
                    sentence_text = sentence.text.lower()
                    if relationship_text and relationship_text in sentence_text:
                        segment_key = (agenda_idx, block_idx, sentence_idx)
                        segment_id = segment_id_lookup.get(segment_key)
                        if segment_id:
                            segment_ids.add(segment_id)
                        continue
                    if source_name in sentence_text or target_name in sentence_text:
                        segment_key = (agenda_idx, block_idx, sentence_idx)
                        segment_id = segment_id_lookup.get(segment_key)
                        if segment_id:
                            segment_ids.add(segment_id)
                        continue
                    if relationship_text and any(
                        word in sentence_text for word in relationship_text.split()
                    ):
                        segment_key = (agenda_idx, block_idx, sentence_idx)
                        segment_id = segment_id_lookup.get(segment_key)
                        if segment_id:
                            segment_ids.add(segment_id)

        return list(segment_ids)

    def _parse_simple_response(self, response: dict[str, Any]) -> SessionTranscript:
        return parse_gemini_transcript_response(response)

    def _generate_session_id(
        self, chamber: str, session_date: date | None, sitting_number: str | None
    ) -> str:
        sitting = sitting_number or "0"
        try:
            # Simplified ordinal stripping using regex
            sitting_num = int(re.sub(r"(st|nd|rd|th)$", "", sitting, flags=re.IGNORECASE))
        except (ValueError, AttributeError):
            sitting_num = 0

        if session_date is None:
            session_date = datetime.now(timezone.utc).date()

        date_str = session_date.strftime("%Y_%m_%d")
        return f"s_{sitting_num}_{date_str}"

    def _generate_speaker_id(self, name: str) -> str:
        parts = name.strip().split()
        if len(parts) >= 2:
            last_name = parts[-1].lower()
            initials = "".join(p[0].lower() for p in parts[:-1])
            return f"p_{last_name}_{initials}"
        return f"p_{name.lower().replace(' ', '_')}"

    def _parse_timecode(self, time_str: str) -> int:
        match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
        if not match:
            return 0
        minutes, seconds, ms = map(int, match.groups())
        return minutes * 60 + seconds

    def _extract_youtube_id(self, url: str) -> str:
        # Security: Limit URL length to prevent ReDoS attacks
        MAX_URL_LENGTH = 2048
        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"URL too long (max {MAX_URL_LENGTH} characters)")

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid YouTube URL scheme: {url}")

        pattern = r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)"
        match = re.search(pattern, url)
        if not match:
            raise ValueError(f"Invalid YouTube URL: {url}")

        youtube_id = match.group(1)
        if not re.match(r"^[a-zA-Z0-9_-]{11}$", youtube_id):
            raise ValueError(f"Invalid YouTube ID format: {youtube_id}")

        return youtube_id

    def _log_run_summary(self, youtube_id: str) -> None:
        logger.info("Timing summary for %s (ms): %s", youtube_id, self.stage_timings_ms)

    async def ingest_from_file(
        self,
        mapping_file: Path,
        fps: float | None = None,
    ) -> list[dict[str, object]]:
        with open(mapping_file) as f:
            videos = json.load(f)

        logger.info(f"Found {len(videos)} videos to ingest")

        results = []
        for i, video_data in enumerate(videos, 1):
            logger.info(f"Processing {i}/{len(videos)}")

            result = await self.ingest_video(
                youtube_url=video_data["youtube_url"],
                chamber=video_data.get("chamber", "house"),
                session_date=datetime.fromisoformat(video_data["session_date"]).date()
                if video_data.get("session_date")
                else None,
                sitting_number=video_data.get("sitting_number"),
                session_id=video_data.get("session_id"),
                fps=fps,
                start_time=int(video_data["start_time"])
                if video_data.get("start_time") is not None
                else None,
                end_time=int(video_data["end_time"])
                if video_data.get("end_time") is not None
                else None,
            )
            results.append(result)

        return results


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest videos to database")
    parser.add_argument("--url", help="YouTube URL to ingest")
    parser.add_argument("--mapping", type=Path, help="JSON file with video metadata")
    parser.add_argument("--chamber", choices=["house", "senate"], default="house", help="Chamber")
    parser.add_argument("--session-date", help="Session date (YYYY-MM-DD)")
    parser.add_argument("--sitting-number", help="Sitting number")
    parser.add_argument("--session-id", help="Stable session ID")
    parser.add_argument("--fps", type=float, help="Frames per second for video sampling")
    parser.add_argument("--start-time", type=int, help="Start time in seconds")
    parser.add_argument("--end-time", type=int, help="End time in seconds")
    parser.add_argument("--no-thinking", action="store_true", help="Disable Gemini thinking")

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
            results = await ingestor.ingest_from_file(args.mapping, args.fps)

            success = sum(1 for r in results if r["status"] == "success")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            failed = sum(1 for r in results if r["status"] == "error")

            print("\nResults:")
            print(f"  Success: {success}")
            print(f"  Skipped: {skipped}")
            print(f"  Failed: {failed}")
        elif args.url:
            result = await ingestor.ingest_video(
                youtube_url=args.url,
                chamber=args.chamber,
                session_date=datetime.fromisoformat(args.session_date).date()
                if args.session_date
                else None,
                sitting_number=args.sitting_number,
                session_id=args.session_id,
                fps=args.fps,
                start_time=args.start_time,
                end_time=args.end_time,
            )
            print(result)
        else:
            parser.print_help()


@asynccontextmanager
async def _db_session() -> AsyncIterator[AsyncSession]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
