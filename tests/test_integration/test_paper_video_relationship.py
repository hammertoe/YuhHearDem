"""Tests for 1:N paper-video relationship (multi-part sessions)."""

import pytest
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from core.database import get_session_maker
from models.video import Video
from models.order_paper import OrderPaper
from services.video_paper_matcher import VideoPaperMatcher, TitlePatternMatcher


@pytest.mark.asyncio
async def test_multiple_videos_can_link_to_one_paper(db_session):
    """One order paper should be able to link to multiple videos."""
    paper = OrderPaper(
        id=uuid4(),
        pdf_path="test.pdf",
        pdf_hash="abc123",
        session_title="Test Session",
        session_date=datetime(2025, 1, 15),
        sitting_number="10th",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    db_session.add(paper)
    await db_session.flush()

    video1 = Video(
        id=uuid4(),
        youtube_id="video1",
        youtube_url="https://youtube.com/watch?v=video1",
        title="Test Session - Part 1",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=paper.id,
    )
    video2 = Video(
        id=uuid4(),
        youtube_id="video2",
        youtube_url="https://youtube.com/watch?v=video2",
        title="Test Session - Part 2",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=paper.id,
    )

    db_session.add(video1)
    db_session.add(video2)
    await db_session.commit()

    result = await db_session.execute(select(Video).where(Video.order_paper_id == paper.id))
    videos = result.scalars().all()

    assert len(videos) == 2
    assert videos[0].youtube_id == "video1"
    assert videos[1].youtube_id == "video2"


@pytest.mark.asyncio
async def test_paper_can_have_no_videos_linked(db_session):
    """Order paper should exist without any linked videos."""
    paper = OrderPaper(
        id=uuid4(),
        pdf_path="test.pdf",
        pdf_hash="abc123",
        session_title="Test Session",
        session_date=datetime(2025, 1, 15),
        sitting_number="10th",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    db_session.add(paper)
    await db_session.commit()

    result = await db_session.execute(select(Video).where(Video.order_paper_id == paper.id))
    videos = result.scalars().all()

    assert len(videos) == 0


@pytest.mark.asyncio
async def test_video_can_be_unlinked_from_paper(db_session):
    """Video should be able to exist without being linked to a paper."""
    video = Video(
        id=uuid4(),
        youtube_id="video1",
        youtube_url="https://youtube.com/watch?v=video1",
        title="Test Session - Part 1",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=None,
    )
    db_session.add(video)
    await db_session.commit()

    result = await db_session.execute(select(Video).where(Video.id == video.id))
    loaded_video = result.scalar_one_or_none()

    assert loaded_video is not None
    assert loaded_video.order_paper_id is None


@pytest.mark.asyncio
async def test_matching_handles_multi_part_videos(db_session):
    """VideoPaperMatcher should be able to match multiple videos to one paper."""
    matcher = VideoPaperMatcher()

    paper = OrderPaper(
        id=uuid4(),
        pdf_path="test.pdf",
        pdf_hash="abc123",
        session_title="THE HONOURABLE THE HOUSE OF ASSEMBLY, FIRST SESSION OF 2022-2027",
        session_date=datetime(2025, 1, 15),
        sitting_number="TENTH SITTING",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    db_session.add(paper)
    await db_session.flush()

    video1_metadata = TitlePatternMatcher.parse_video_title(
        "The Honourable The House - Tuesday 15th January, 2025 - Part 1"
    )
    video1_metadata.youtube_id = "video1"

    video2_metadata = TitlePatternMatcher.parse_video_title(
        "The Honourable The House - Tuesday 15th January, 2025 - Part 2"
    )
    video2_metadata.youtube_id = "video2"

    papers = [paper]

    result1 = matcher.match_video(video1_metadata, papers, auto_accept_threshold=75)
    assert result1.matched_paper_id == paper.id
    assert not result1.is_ambiguous

    result2 = matcher.match_video(video2_metadata, papers, auto_accept_threshold=75)
    assert result2.matched_paper_id == paper.id
    assert not result2.is_ambiguous

    assert result1.matched_paper_id == result2.matched_paper_id


@pytest.mark.asyncio
async def test_can_link_multiple_videos_to_existing_paper(db_session):
    """Should be able to link multiple videos to an existing paper."""
    paper = OrderPaper(
        id=uuid4(),
        pdf_path="test.pdf",
        pdf_hash="abc123",
        session_title="Test Session",
        session_date=datetime(2025, 1, 15),
        sitting_number="10th",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    db_session.add(paper)
    await db_session.flush()

    video1 = Video(
        id=uuid4(),
        youtube_id="video1",
        youtube_url="https://youtube.com/watch?v=video1",
        title="Test Session - Part 1",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=None,
    )
    db_session.add(video1)
    await db_session.commit()

    video1.order_paper_id = paper.id
    await db_session.commit()

    video2 = Video(
        id=uuid4(),
        youtube_id="video2",
        youtube_url="https://youtube.com/watch?v=video2",
        title="Test Session - Part 2",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=None,
    )
    db_session.add(video2)
    await db_session.commit()

    video2.order_paper_id = paper.id
    await db_session.commit()

    result = await db_session.execute(select(Video).where(Video.order_paper_id == paper.id))
    videos = result.scalars().all()

    assert len(videos) == 2
    assert set([v.youtube_id for v in videos]) == {"video1", "video2"}


@pytest.mark.asyncio
async def test_video_belongs_to_one_paper_at_most(db_session):
    """A video should belong to at most one paper."""
    paper1 = OrderPaper(
        id=uuid4(),
        pdf_path="test1.pdf",
        pdf_hash="abc123",
        session_title="Test Session 1",
        session_date=datetime(2025, 1, 15),
        sitting_number="10th",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    paper2 = OrderPaper(
        id=uuid4(),
        pdf_path="test2.pdf",
        pdf_hash="def456",
        session_title="Test Session 2",
        session_date=datetime(2025, 1, 16),
        sitting_number="11th",
        chamber="house",
        speakers=[],
        agenda_items=[],
    )
    db_session.add(paper1)
    db_session.add(paper2)
    await db_session.flush()

    video = Video(
        id=uuid4(),
        youtube_id="video1",
        youtube_url="https://youtube.com/watch?v=video1",
        title="Test Session - Part 1",
        chamber="house",
        session_date=datetime(2025, 1, 15),
        order_paper_id=paper1.id,
    )
    db_session.add(video)
    await db_session.commit()

    video.order_paper_id = paper2.id
    await db_session.commit()

    result = await db_session.execute(select(Video).where(Video.id == video.id))
    loaded_video = result.scalar_one_or_none()

    assert loaded_video.order_paper_id == paper2.id
