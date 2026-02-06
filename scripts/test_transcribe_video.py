#!/usr/bin/env python3
"""Quick test: Add a YouTube video and transcribe it"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select

from core.database import get_db
from models.session import Session as SessionModel
from models.video import Video
from parsers.models import OrderPaper
from services.gemini import GeminiClient
from services.video_transcription import VideoTranscriptionService

TEST_VIDEO_URL = "https://www.youtube.com/watch?v=P6cUJb9xqIs"  # Sample video


async def main() -> None:
    print("Adding video to database...")

    async for db in get_db():
        # Check if video already exists
        existing = await db.execute(select(Video).where(Video.video_id == "P6cUJb9xqIs"))

        if existing.scalar_one_or_none():
            print("Video already exists in database")
            video = existing.scalar_one()
        else:
            # Create new video record
            session_id = f"s_0_{datetime.now(timezone.utc).date().strftime('%Y_%m_%d')}"
            session = SessionModel(
                session_id=session_id,
                date=datetime.now(timezone.utc).date(),
                title="House of Assembly Sitting",
                sitting_number="0",
                chamber="house",
            )
            db.add(session)
            await db.flush()

            video = Video(
                video_id="P6cUJb9xqIs",
                session_id=session_id,
                platform="youtube",
                url=TEST_VIDEO_URL,
                duration_seconds=None,
            )
            db.add(video)
            await db.commit()
            print(f"✓ Video added: {video.video_id}")
            # Refresh to get ID
            await db.refresh(video)

        # Transcribe the video
        print("\nTranscribing video...")
        client = GeminiClient(temperature=0.0)
        service = VideoTranscriptionService(client)

        order_paper = OrderPaper(
            session_title="House of Assembly Sitting",
            session_date=datetime.now(timezone.utc).date(),
            speakers=[],
            agenda_items=[],
        )

        transcript = service.transcribe(
            video_url=TEST_VIDEO_URL,
            order_paper=order_paper,
            speaker_id_mapping={},
            fps=0.25,
        )

        print("✓ Transcription complete!")
        print(f"  - {len(transcript.agenda_items)} agenda items")
        print(f"  - Session title: {transcript.session_title}")

        print("✓ Transcription completed without DB persistence")


if __name__ == "__main__":
    asyncio.run(main())
