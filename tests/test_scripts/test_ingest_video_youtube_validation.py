"""Tests for YouTube URL validation in ingest_video."""

import pytest

from scripts.ingest_video import VideoIngestor


def test_extract_youtube_id_rejects_invalid_scheme(mock_db):
    """Invalid URL schemes should raise ValueError."""
    ingestor = VideoIngestor(db_session=mock_db, gemini_client=None)

    with pytest.raises(ValueError):
        ingestor._extract_youtube_id("ftp://youtube.com/watch?v=Syxyah7QIaM")


def test_extract_youtube_id_rejects_invalid_id_length(mock_db):
    """Invalid YouTube ID lengths should raise ValueError."""
    ingestor = VideoIngestor(db_session=mock_db, gemini_client=None)

    with pytest.raises(ValueError):
        ingestor._extract_youtube_id("https://youtu.be/short")


def test_extract_youtube_id_accepts_valid_url(mock_db):
    """Valid YouTube URLs should return the video ID."""
    ingestor = VideoIngestor(db_session=mock_db, gemini_client=None)

    youtube_id = ingestor._extract_youtube_id("https://youtu.be/Syxyah7QIaM")

    assert youtube_id == "Syxyah7QIaM"
