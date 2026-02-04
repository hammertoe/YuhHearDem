"""Test video API endpoints."""

from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from models.video import Video


class TestVideoEndpoints:
    """Video API coverage."""

    @pytest.mark.asyncio
    async def test_create_video_without_transcript(self, client: AsyncClient, db_session):
        """Videos can be created without transcripts (deferred processing)."""
        payload = {
            "youtube_id": "abc123",
            "youtube_url": "https://youtube.com/watch?v=abc123",
            "title": "Test Session",
            "chamber": "house",
            "session_date": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

        response = await client.post("/api/videos/", json=payload)

        assert response.status_code == 202

        data = response.json()
        video_id = UUID(data["video_id"])

        result = await db_session.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one()

        assert video.transcript is None

    @pytest.mark.asyncio
    async def test_list_videos_applies_pagination(self, client: AsyncClient, db_session):
        """Pagination parameters should limit results."""
        videos = [
            Video(
                youtube_id="v1",
                youtube_url="https://youtube.com/watch?v=v1",
                title="Session 1",
                chamber="house",
                session_date=datetime(2024, 1, 1),
                transcript={},
            ),
            Video(
                youtube_id="v2",
                youtube_url="https://youtube.com/watch?v=v2",
                title="Session 2",
                chamber="house",
                session_date=datetime(2024, 1, 2),
                transcript={},
            ),
            Video(
                youtube_id="v3",
                youtube_url="https://youtube.com/watch?v=v3",
                title="Session 3",
                chamber="house",
                session_date=datetime(2024, 1, 3),
                transcript={},
            ),
        ]

        db_session.add_all(videos)
        await db_session.commit()

        response = await client.get("/api/videos/", params={"page": 1, "per_page": 2})

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
