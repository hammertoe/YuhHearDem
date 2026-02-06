"""Tests for shared transcript response parsing."""

from datetime import datetime

from parsers.transcript_models import parse_gemini_transcript_response


def test_parse_transcript_defaults_chamber():
    """Missing chamber should default to house."""
    response = {"session_title": "Test Session", "agenda_items": []}

    transcript = parse_gemini_transcript_response(response)

    assert transcript.chamber == "house"


def test_parse_transcript_builds_sentence_objects():
    """Sentences should be parsed into dataclass objects."""
    response = {
        "session_title": "Test Session",
        "agenda_items": [
            {
                "topic_title": "Opening",
                "speech_blocks": [
                    {
                        "speaker_name": "Hon. Jane Doe",
                        "sentences": [{"start_time": "0m0s0ms", "text": "Welcome."}],
                    }
                ],
            }
        ],
    }

    transcript = parse_gemini_transcript_response(response)

    assert transcript.agenda_items[0].speech_blocks[0].sentences[0].text == "Welcome."


def test_parse_transcript_sets_date_when_missing():
    """Missing date should set a valid datetime value."""
    response = {"session_title": "Test Session", "agenda_items": []}

    transcript = parse_gemini_transcript_response(response)

    assert isinstance(transcript.date, datetime)
