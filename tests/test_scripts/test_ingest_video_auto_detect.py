"""Tests for auto-detecting session metadata from video."""

from unittest.mock import MagicMock, patch

from scripts.ingest_video import VideoIngestor
from scripts.ingest_video import VideoMetadata
from datetime import date


def test_auto_detect_session_date_from_video_metadata():
    """Extract session metadata from YouTube video using LLM."""

    ingestor = VideoIngestor(db_session=MagicMock(), gemini_client=MagicMock())

    mock_metadata = VideoMetadata(
        session_date=date(2026, 1, 6),
        chamber="house",
        title="House of Assembly - Sitting 11",
        sitting_number="11",
    )

    with patch.object(ingestor, "_extract_metadata_with_llm", return_value=mock_metadata):
        with patch("scripts.ingest_video.yt_dlp") as mock_ydl:
            mock_ydl.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
                "title": "Test Video",
                "description": "Test description",
                "upload_date": "20260106",
            }

            detected_date, detected_chamber, detected_title, detected_sitting = (
                ingestor._auto_detect_session_date("https://www.youtube.com/watch?v=test123")
            )

            assert detected_date == date(2026, 1, 6)
            assert detected_chamber == "house"
            assert detected_title == "House of Assembly - Sitting 11"
            assert detected_sitting == "11"


def test_auto_detect_session_date_handles_missing_metadata():
    """Return None when metadata extraction fails."""

    ingestor = VideoIngestor(db_session=MagicMock(), gemini_client=MagicMock())

    with patch.object(
        ingestor,
        "_extract_metadata_with_llm",
        return_value=VideoMetadata(
            session_date=None, chamber=None, title=None, sitting_number=None
        ),
    ):
        with patch("scripts.ingest_video.yt_dlp") as mock_ydl:
            mock_ydl.YoutubeDL.return_value.__enter__.return_value.extract_info.return_value = {
                "title": "Test Video",
                "description": "",
                "upload_date": "20260106",
            }

            detected_date, detected_chamber, detected_title, detected_sitting = (
                ingestor._auto_detect_session_date("https://www.youtube.com/watch?v=test123")
            )

            assert detected_date is None
            assert detected_chamber is None
            assert detected_title is None
            assert detected_sitting is None
