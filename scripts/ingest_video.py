#!/usr/bin/env python3
"""Ingest videos to database with transcription"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from models.speaker import Speaker
from models.video import Video as VideoModel
from parsers.models import OrderPaper as ParsedOrderPaper
from services.entity_extractor import EntityExtractor
from services.gemini import GeminiClient
from services.video_transcription import VideoTranscriptionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class VideoIngestor:
    """Ingests videos into database"""

    def __init__(
        self,
        db_session: AsyncSession,
        gemini_client: GeminiClient,
        entity_extractor: EntityExtractor | None = None,
    ):
        self.db = db_session
        self.client = gemini_client
        self.transcription_service = VideoTranscriptionService(gemini_client)
        self.entity_extractor = entity_extractor or EntityExtractor()

    async def ingest_video(
        self,
        youtube_url: str,
        chamber: str = "house",
        session_date: datetime | None = None,
        sitting_number: str | None = None,
        order_paper: ParsedOrderPaper | None = None,
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

        youtube_id = self._extract_youtube_id(youtube_url)

        logger.info(f"Ingesting video: {youtube_id}")

        # Check if already exists
        existing = await self.db.execute(
            select(VideoModel).where(VideoModel.youtube_id == youtube_id)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Video already exists: {youtube_id}")
            return {"status": "skipped", "reason": "already_exists"}

        try:
            # Build speaker ID mapping from database
            speaker_id_mapping = await self._get_speaker_id_mapping()

            # Transcribe video
            if order_paper:
                transcript = self.transcription_service.transcribe(
                    video_url=youtube_url,
                    order_paper=order_paper,
                    speaker_id_mapping=speaker_id_mapping,
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
                    fps=0.25,
                )

                transcript = self._parse_simple_response(response)

            # Extract entities from transcript
            entities = []
            if transcript and hasattr(transcript, "agenda_items"):
                for item in transcript.agenda_items:
                    for speech in item.speech_blocks:
                        text = " ".join([s.text for s in speech.sentences])
                        entities.extend(self.entity_extractor.extract_entities(text))

            # Save to database
            video = VideoModel(
                youtube_id=youtube_id,
                youtube_url=youtube_url,
                title=transcript.session_title or f"Session {youtube_id}",
                chamber=chamber,
                session_date=session_date or datetime.utcnow(),
                sitting_number=sitting_number,
                transcript=transcript.model_dump() if hasattr(transcript, "model_dump") else {},
                transcript_processed_at=datetime.utcnow(),
            )

            self.db.add(video)
            await self.db.commit()
            await self.db.refresh(video)

            logger.info(f"Saved video: {video.id}")

            return {
                "status": "success",
                "video_id": str(video.id),
                "youtube_id": youtube_id,
                "entities_count": len(entities),
            }

        except Exception as e:
            logger.error(f"Failed to ingest video: {e}")
            await self.db.rollback()
            return {"status": "error", "error": str(e)}

    async def ingest_from_file(
        self,
        mapping_file: Path,
    ) -> list[dict]:
        """
        Ingest videos from a JSON mapping file.

        Args:
            mapping_file: JSON file with video metadata

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
            )
            results.append(result)

        return results

    async def _get_speaker_id_mapping(self) -> dict[str, str]:
        """Build mapping of speaker names to IDs"""
        result = await self.db.execute(select(Speaker))
        speakers = result.scalars().all()

        return {s.name: str(s.id) for s in speakers}

    def _extract_youtube_id(self, url: str) -> str:
        """Extract YouTube ID from URL"""
        pattern = r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)"
        import re

        match = re.search(pattern, url)
        if not match:
            raise ValueError(f"Invalid YouTube URL: {url}")
        return match.group(1)

    def _parse_simple_response(self, response: dict) -> object:
        """Parse Gemini response without order paper"""
        from parsers.transcript_models import SessionTranscript

        return SessionTranscript(
            session_title=response.get("title", "Unknown Session"),
            date=datetime.utcnow(),
            chamber="house",
            agenda_items=[],
            video_url=response.get("video_url"),
            video_title=response.get("video_title"),
        )


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
        "--order-paper",
        type=Path,
        help="Path to order paper PDF for context",
    )

    args = parser.parse_args()

    settings = get_settings()

    from google import genai

    from app.dependencies import get_db_session

    genai.configure(api_key=settings.google_api_key)
    client = GeminiClient()
    extractor = EntityExtractor()

    async with get_db_session() as db:
        ingestor = VideoIngestor(db, client, extractor)

        if args.mapping:
            results = await ingestor.ingest_from_file(args.mapping)

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
                session_date=datetime.fromisoformat(args.session_date)
                if args.session_date
                else None,
                sitting_number=args.sitting_number,
            )
            print(result)
        else:
            parser.print_help()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
