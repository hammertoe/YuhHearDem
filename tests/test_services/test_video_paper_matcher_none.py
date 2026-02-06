"""Tests for VideoPaperMatcher handling of missing metadata."""

from datetime import date

from services.video_paper_matcher import VideoMetadata, VideoPaperMatcher


def test_find_candidates_handles_missing_chamber():
    """Missing chamber should return no candidates without error."""
    matcher = VideoPaperMatcher()
    video = VideoMetadata(
        youtube_id="abc",
        title="House of Assembly - 1 January 2026",
        description="",
        extracted_session_date=date(2026, 1, 1),
        extracted_chamber=None,
        extracted_sitting=None,
    )

    candidates = matcher._find_candidates(video, [])

    assert candidates == []


def test_calculate_match_score_handles_missing_chamber():
    """Missing chamber should not affect date scoring."""
    matcher = VideoPaperMatcher()
    video = VideoMetadata(
        youtube_id="abc",
        title="House of Assembly - 1 January 2026",
        description="",
        extracted_session_date=date(2026, 1, 1),
        extracted_chamber=None,
        extracted_sitting=None,
    )
    paper = {"session_date": date(2026, 1, 1), "chamber": "house"}

    score = matcher._calculate_match_score(video, paper)

    assert score == 50
