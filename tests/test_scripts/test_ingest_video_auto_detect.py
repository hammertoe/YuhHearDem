"""Tests for auto-detecting session date from order paper."""

from datetime import date

from scripts.ingest_video import VideoIngestor
from models.session import Session as SessionModel


async def test_auto_detect_session_date_from_most_recent_order_paper(db_session):
    """Auto-detect session_date from most recent order paper when not provided."""

    ingestor = VideoIngestor(db_session=db_session, gemini_client=None)

    chamber = "house"

    existing_order_paper_1 = SessionModel(
        session_id="s_10_2025_12_15",
        date=date(2025, 12, 15),
        title=f"{chamber.title()} Parliamentary Session",
        sitting_number="10",
        chamber=chamber,
    )
    existing_order_paper_2 = SessionModel(
        session_id="s_11_2026_01_06",
        date=date(2026, 1, 6),
        title=f"{chamber.title()} Parliamentary Session",
        sitting_number="11",
        chamber=chamber,
    )
    db_session.add(existing_order_paper_1)
    db_session.add(existing_order_paper_2)
    await db_session.commit()

    auto_detected_date = await ingestor._auto_detect_session_date(chamber)

    assert auto_detected_date == date(2026, 1, 6)


async def test_auto_detect_session_date_returns_none_when_no_order_papers(db_session):
    """Return None when no order papers exist for chamber."""

    ingestor = VideoIngestor(db_session=db_session, gemini_client=None)

    auto_detected_date = await ingestor._auto_detect_session_date("house")

    assert auto_detected_date is None
