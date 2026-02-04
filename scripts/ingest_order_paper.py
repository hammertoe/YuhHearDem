#!/usr/bin/env python3
"""Ingest order papers to database"""

import argparse
import hashlib
import logging
import sys
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from core.database import Base
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

    def __init__(self, gemini_client: GeminiClient):
        self.client = gemini_client
        self.parser = OrderPaperParser(gemini_client=self.client)

    async def ingest_pdf(
        self,
        db_session_maker: async_sessionmaker,
        pdf_path: Path,
        video_id: Optional[str] = None,
        chamber: str = "house",
    ) -> dict:
        """
        Parse and save an order paper PDF.

        Args:
            db_session_maker: Session maker
            pdf_path: Path to PDF file
            video_id: Associated YouTube video ID (optional, no longer used)
            chamber: Chamber ('house' or 'senate')

        Returns:
            Dictionary with ingest status and IDs
        """
        logger.info(f"Ingesting: {pdf_path.name}")

        async with db_session_maker() as db:
            # Check if already ingested
            pdf_hash = self._calculate_hash(pdf_path)
            existing = await db.execute(
                select(OrderPaperModel).where(OrderPaperModel.pdf_hash == pdf_hash)
            )
            existing_record = existing.scalar_one_or_none()
            if existing_record:
                logger.info(f"Already ingested: {pdf_path.name}")
                await self._sync_speakers_from_record(db, existing_record)
                return {"status": "skipped", "reason": "already_exists"}

            # Parse PDF
            try:
                parsed: ParsedOrderPaper = self.parser.parse(pdf_path)

                logger.info(
                    f"Parsed {len(parsed.speakers)} speakers, {len(parsed.agenda_items)} agenda items"
                )

                # Save to database
                order_paper = OrderPaperModel(
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

                db.add(order_paper)
                await db.commit()
                await db.refresh(order_paper)

                logger.info(f"Saved order paper: {order_paper.id}")

                # Create/update speakers
                await self._sync_speakers(db, parsed.speakers)

                return {
                    "status": "success",
                    "order_paper_id": str(order_paper.id),
                }

            except Exception as e:
                logger.error(f"Failed to ingest {pdf_path}: {e}")
                await db.rollback()
                return {"status": "error", "error": str(e)}

    async def _sync_speakers(self, db: AsyncSession, speakers: list):
        """Create or update speaker records"""
        if not speakers:
            return

        from services.speaker_matcher import SpeakerMatcher

        matcher = SpeakerMatcher()

        for speaker_data in speakers:
            result = await db.execute(select(Speaker).where(Speaker.name == speaker_data.name))
            speaker = result.scalar_one_or_none()

            if not speaker:
                speaker = Speaker(
                    canonical_id=matcher.normalize_name(speaker_data.name),
                    name=speaker_data.name,
                    title=speaker_data.title,
                    role=speaker_data.role,
                    aliases=[],
                    meta_data={},
                )
                db.add(speaker)

        await db.commit()

    async def _sync_speakers_from_record(self, db: AsyncSession, record: OrderPaperModel):
        """Sync speakers from an existing order paper record"""
        if not record.speakers:
            return

        from types import SimpleNamespace

        speakers = [
            SimpleNamespace(
                name=s.get("name"),
                title=s.get("title"),
                role=s.get("role"),
            )
            for s in record.speakers
            if s.get("name")
        ]

        await self._sync_speakers(db, speakers)

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    async def ingest_directory(
        self,
        db_session_maker: async_sessionmaker,
        pdf_dir: Path,
        video_mapping: Optional[dict] = None,
        chamber: str = "house",
    ) -> list[dict]:
        """
        Ingest all PDFs from directory.

        Args:
            db_session_maker: Session maker
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

            result = await self.ingest_pdf(db_session_maker, pdf_path, video_id, chamber)
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

    import google.genai as genai

    client = GeminiClient(api_key=settings.google_api_key)

    # Create database engine and session maker
    engine = create_async_engine(settings.database_url)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    ingestor = OrderPaperIngestor(client)

    if args.pdf_path.is_file():
        result = await ingestor.ingest_pdf(
            session_maker, args.pdf_path, args.video_id, args.chamber
        )
        print(result)
    elif args.pdf_path.is_dir():
        video_mapping = {}
        if args.video_mapping and args.video_mapping.exists():
            import json

            video_mapping = json.loads(args.video_mapping.read_text())

        results = await ingestor.ingest_directory(
            session_maker, args.pdf_path, video_mapping, args.chamber
        )

        success = sum(1 for r in results if r["status"] == "success")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] == "error")

        print(f"\nResults:")
        print(f"  Success: {success}")
        print(f"  Skipped: {skipped}")
        print(f"  Failed: {failed}")
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
