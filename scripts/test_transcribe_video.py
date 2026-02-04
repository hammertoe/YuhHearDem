#!/usr/bin/env python3
"""Quick test: Add a YouTube video and transcribe it"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from app.dependencies import get_db_session
from models.video import Video
from services.video_transcription import VideoTranscriptionService
from services.gemini import GeminiClient
from dataclasses import asdict

TEST_VIDEO_URL = "https://www.youtube.com/watch?v=P6cUJb9xqIs"  # Sample video


async def main():
    print("Adding video to database...")

    async for db in get_db_session():
        # Check if video already exists
        existing = await db.execute(select(Video).where(Video.youtube_id == "P6cUJb9xqIs"))

        if existing.scalar_one_or_none():
            print("Video already exists in database")
            video = existing.scalar_one()
        else:
            # Create new video record
            from datetime import datetime

            video = Video(
                youtube_id="P6cUJb9xqIs",
                youtube_url=TEST_VIDEO_URL,
                title="Test Video for Transcription",
                chamber="house",
                session_date=datetime.utcnow(),  # Required field
                sitting_number=None,
                transcript={},  # Empty transcript initially
            )
            db.add(video)
            await db.commit()
            print(f"✓ Video added: {video.title}")
            # Refresh to get ID
            await db.refresh(video)

        # Transcribe the video
        print(f"\nTranscribing video...")
        client = GeminiClient(temperature=0.0)
        service = VideoTranscriptionService(client)

        transcript = await service.transcribe(
            video_url=TEST_VIDEO_URL, order_paper=None, speaker_id_mapping={}, fps=0.25
        )

        print(f"✓ Transcription complete!")
        print(f"  - {len(transcript.agenda_items)} agenda items")
        print(f"  - Session title: {transcript.session_title}")

        # Save transcript back to video
        video.transcript = asdict(transcript)
        await db.commit()
        print(f"✓ Transcript saved to database")


if __name__ == "__main__":
    asyncio.run(main())
