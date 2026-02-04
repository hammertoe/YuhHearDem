"""Tests for the video transcript parser."""

from datetime import datetime, timezone

from parsers.transcript_models import Sentence, SessionTranscript, SpeechBlock, TranscriptAgendaItem
from parsers.video_transcript import VideoTranscriptionParser


def test_validate_and_filter_timestamps_handles_invalid_timecode():
    """Invalid timecodes should not raise and should be filtered out."""
    parser = VideoTranscriptionParser(gemini_client=None)
    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Intro",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Speaker",
                        sentences=[Sentence(start_time="bad", text="Hello")],
                    )
                ],
            )
        ],
    )

    result = parser._validate_and_filter_timestamps(
        transcript,
        expected_start=0,
        expected_end=60,
    )

    assert result.agenda_items == []
