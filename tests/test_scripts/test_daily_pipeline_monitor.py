"""Tests for daily pipeline YouTube monitoring."""

from datetime import datetime
import types

import pytest
from sqlalchemy import select

from models.video import Video


@pytest.mark.asyncio
async def test_monitor_youtube_creates_video_without_transcript(db_session_maker, monkeypatch):
    """Monitor step should persist new videos without transcripts."""
    from scripts import daily_pipeline as dp

    class FakeYDL:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=False):
            return {
                "entries": [
                    {
                        "id": "abc123",
                        "title": "House of Assembly - 15 January 2024",
                        "description": "",
                        "duration": 120,
                    }
                ]
            }

    fake_module = types.SimpleNamespace(YoutubeDL=FakeYDL)
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", fake_module)
    monkeypatch.setattr(dp, "get_session_maker", lambda: db_session_maker)

    pipeline = dp.DailyPipeline(dry_run=False)
    await pipeline.monitor_youtube()

    async with db_session_maker() as db:
        result = await db.execute(select(Video).where(Video.youtube_id == "abc123"))
        video = result.scalar_one()

    assert video.transcript is None
    assert isinstance(video.session_date, datetime)
