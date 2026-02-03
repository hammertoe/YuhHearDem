#!/usr/bin/env python3
"""Ingest order papers to database"""

import argparse
import hashlib
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from models.order_paper import OrderPaper as OrderPaperModel
from models.speaker import Speaker
from models.video import Video
from parsers.models import OrderPaper as ParsedOrderPaper
from parsers.order_paper_parser import OrderPaperParser
from services.gemini import GeminiClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class OrderPaperIngestor:
    """Ingests order papers into database"""

    def __init__(self, db_session: AsyncSession, gemini_client: GeminiClient):
        self.db = db_session
        self.client = gemini_client
        self.parser = OrderPaperParser(gemini_client=client)

    async def ingest_pdf(
        self,
        pdf_path: Path,
        video_id: str | None = None,
        chamber: str = "house",
    ) -> dict:
        """
        Parse and save an order paper PDF.

        Args:
            pdf_path: Path to PDF file
            video_id: Associated YouTube video ID (optional)
            chamber: Chamber ('house' or 'senate')

        Returns:
            Dictionary with ingest status and IDs
        """
        logger.info(f"Ingesting: {pdf_path.name}")

        # Check if already ingested
        pdf_hash = self._calculate_hash(pdf_path)
        existing = await self.db.execute(
            select(OrderPaperModel).where(OrderPaperModel.pdf_hash == pdf_hash)
        )
        if existing.scalar_one_or_none():
            logger.info(f"Already ingested: {pdf_path.name}")
            return {"status": "skipped", "reason": "already_exists"}

        # Parse PDF
        try:
            parsed: ParsedOrderPaper = self.parser.parse(pdf_path)

            logger.info(
                f"Parsed {len(parsed.speakers)} speakers, {len(parsed.agenda_items)} agenda items"
            )

            # Get or create video record
            video_uuid = None
            if video_id:
                video_uuid = await self._get_or_create_video(video_id, parsed, chamber)

            # Save to database
            order_paper = OrderPaperModel(
                video_id=video_uuid,
                pdf_path=str(pdf_path),
                pdf_hash=pdf_hash,
                session_title=parsed.session_title,
                session_date=datetime.combine(parsed.session_date, datetime.min.time()),
                sitting_number=parsed.sitting_number,
                chamber=chamber,
                speakers=[
                    {
                        "name": s.name,
                        "title": s.title,
                        "role": s.role,
                    }
                    for s in (parsed.speakers or [])
                ],
                agenda_items=[
                    {
                        "topic_title": a.topic_title,
                        "primary_speaker": a.primary_speaker,
                        "description": a.description,
                    }
                    for a in (parsed.agenda_items or [])
                ],
            )

            self.db.add(order_paper)
            await self.db.commit()
            await self.db.refresh(order_paper)

            logger.info(f"Saved order paper: {order_paper.id}")

            # Create/update speakers
            await self._sync_speakers(parsed.speakers)

            return {
                "status": "success",
                "order_paper_id": str(order_paper.id),
                "video_id": str(video_uuid) if video_uuid else None,
            }

        except Exception as e:
            logger.error(f"Failed to ingest {pdf_path}: {e}")
            await self.db.rollback()
            return {"status": "error", "error": str(e)}

    async def _get_or_create_video(
        self,
        youtube_id: str,
        parsed: ParsedOrderPaper,
        chamber: str,
    ) -> str | None:
        """Get or create video record"""
        result = await self.db.execute(select(Video).where(Video.youtube_id == youtube_id))
        video = result.scalar_one_or_none()

        if video:
            return video.id

        # Create new video record
        video = Video(
            youtube_id=youtube_id,
            youtube_url=f"https://www.youtube.com/watch?v={youtube_id}",
            title=parsed.session_title,
            chamber=chamber,
            session_date=datetime.combine(parsed.session_date, datetime.min.time()),
            transcript={},
        )

        self.db.add(video)
        await self.db.commit()
        await self.db.refresh(video)

        return video.id

    async def _sync_speakers(self, speakers: list):
        """Create or update speaker records"""
        if not speakers:
            return

        from services.speaker_matcher import SpeakerMatcher

        matcher = SpeakerMatcher()

        for speaker_data in speakers:
            result = await self.db.execute(select(Speaker).where(Speaker.name == speaker_data.name))
            speaker = result.scalar_one_or_none()

            if not speaker:
                speaker = Speaker(
                    name=speaker_data.name,
                    title=speaker_data.title,
                    role=speaker_data.role,
                    canonical_name=matcher.normalize_name(speaker_data.name),
                )
                self.db.add(speaker)

        await self.db.commit()

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    async def ingest_directory(
        self,
        pdf_dir: Path,
        video_mapping: dict | None = None,
        chamber: str = "house",
    ) -> list[dict]:
        """
        Ingest all PDFs from directory.

        Args:
            pdf_dir: Directory containing PDFs
            video_mapping: Dict mapping PDF filenames to YouTube IDs
            chamber: Chamber

        Returns:
            List of results for each PDF
        """
        pdf_files = list(pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        results = []
        for pdf_path in pdf_files:
            video_id = None
            if video_mapping and pdf_path.name in video_mapping:
                video_id = video_mapping[pdf_path.name]

            result = await self.ingest_pdf(pdf_path, video_id, chamber)
            results.append({**result, "pdf_path": str(pdf_path)})

        return results


async def main():
    parser = argparse.ArgumentParser(description="Ingest order papers to database")
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to PDF file or directory",
    )
    parser.add_argument(
        "--video-id",
        help="YouTube video ID (optional)",
    )
    parser.add_argument(
        "--video-mapping",
        type=Path,
        help="JSON file mapping PDF names to YouTube IDs",
    )
    parser.add_argument(
        "--chamber",
        choices=["house", "senate"],
        default="house",
        help="Chamber (default: house)",
    )

    args = parser.parse_args()

    settings = get_settings()

    from google import genai

    from app.dependencies import get_db_session

    genai.configure(api_key=settings.google_api_key)
    client = GeminiClient()

    async with get_db_session() as db:
        ingestor = OrderPaperIngestor(db, client)

        if args.pdf_path.is_file():
            result = await ingestor.ingest_pdf(args.pdf_path, args.video_id, args.chamber)
            print(result)
        elif args.pdf_path.is_dir():
            video_mapping = {}
            if args.video_mapping and args.video_mapping.exists():
                import json

                video_mapping = json.loads(args.video_mapping.read_text())

            results = await ingestor.ingest_directory(args.pdf_path, video_mapping, args.chamber)

            success = sum(1 for r in results if r["status"] == "success")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            failed = sum(1 for r in results if r["status"] == "error")

            print("\nResults:")
            print(f"  Success: {success}")
            print(f"  Skipped: {skipped}")
            print(f"  Failed: {failed}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
