"""Test stable ID generation for sessions and segments"""

from datetime import datetime

import pytest
from sqlalchemy import select

from core.database import Base, get_engine
from models.session import Session as SessionModel
from models.video import Video
from models.transcript_segment import TranscriptSegment
from models.speaker import Speaker


@pytest.mark.asyncio
async def test_session_id_format_sitting_number_date(db_session):
    """Test that session_id follows format: s_{sitting_number}_{YYYY_MM_DD}"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.commit()

    result = await db_session.execute(
        select(SessionModel).where(SessionModel.session_id == "s_125_2026_01_06")
    )
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.session_id == "s_125_2026_01_06"
    assert fetched.sitting_number == "125"
    assert fetched.date.year == 2026
    assert fetched.date.month == 1
    assert fetched.date.day == 6


@pytest.mark.asyncio
async def test_segment_id_format(db_session):
    """Test that segment_id follows format: {youtube_id}_{start_time_seconds:05d}"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    video = Video(
        video_id="Syxyah7QIaM",
        session_id="s_125_2026_01_06",
        platform="youtube",
        url="https://www.youtube.com/watch?v=Syxyah7QIaM",
        duration_seconds=3600,
    )
    db_session.add(video)
    await db_session.flush()

    speaker = Speaker(
        speaker_id="p_bradshaw",
        name="John Bradshaw",
        title="Honourable",
        role="Member of Parliament",
        chamber="house",
        aliases=[],
    )
    db_session.add(speaker)
    await db_session.flush()

    segment = TranscriptSegment(
        segment_id="Syxyah7QIaM_00395",
        session_id="s_125_2026_01_06",
        video_id="Syxyah7QIaM",
        speaker_id="p_bradshaw",
        start_time_seconds=395,
        end_time_seconds=420,
        text="We also have accompanying Road Traffic Act...",
        speech_block_index=0,
        segment_index=0,
    )
    db_session.add(segment)
    await db_session.commit()

    result = await db_session.execute(
        select(TranscriptSegment).where(TranscriptSegment.segment_id == "Syxyah7QIaM_00395")
    )
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.segment_id == "Syxyah7QIaM_00395"
    assert fetched.video_id == "Syxyah7QIaM"
    assert fetched.start_time_seconds == 395
    assert fetched.end_time_seconds == 420
    assert fetched.segment_index == 0


@pytest.mark.asyncio
async def test_segment_id_zero_padding(db_session):
    """Test that segment_id zero-pads start_time_seconds to 5 digits"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    video = Video(
        video_id="Syxyah7QIaM",
        session_id="s_125_2026_01_06",
        platform="youtube",
        url="https://www.youtube.com/watch?v=Syxyah7QIaM",
        duration_seconds=3600,
    )
    db_session.add(video)
    await db_session.flush()

    speaker = Speaker(
        speaker_id="p_bradshaw",
        name="John Bradshaw",
        title="Honourable",
        role="Member of Parliament",
        chamber="house",
        aliases=[],
    )
    db_session.add(speaker)
    await db_session.flush()

    segment = TranscriptSegment(
        segment_id="Syxyah7QIaM_00123",
        session_id="s_125_2026_01_06",
        video_id="Syxyah7QIaM",
        speaker_id="p_bradshaw",
        start_time_seconds=123,
        end_time_seconds=148,
        text="Sample text",
        speech_block_index=0,
        segment_index=0,
    )
    db_session.add(segment)
    await db_session.commit()

    result = await db_session.execute(
        select(TranscriptSegment).where(TranscriptSegment.segment_id == "Syxyah7QIaM_00123")
    )
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.segment_id == "Syxyah7QIaM_00123"
    assert fetched.start_time_seconds == 123
