"""Tests for ingest_video simple response parsing."""

from parsers.transcript_models import Sentence
from scripts.ingest_video import VideoIngestor


def test_parse_simple_response_includes_agenda_items(mock_db):
    """Simple response parsing should map agenda items and sentences."""
    ingestor = VideoIngestor(db_session=mock_db, gemini_client=None)

    response = {
        "session_title": "Test Session",
        "chamber": "house",
        "agenda_items": [
            {
                "topic_title": "Opening",
                "speech_blocks": [
                    {
                        "speaker_name": "Hon. Jane Doe",
                        "sentences": [{"start_time": "0m1s0ms", "text": "Good morning."}],
                    }
                ],
            }
        ],
    }

    transcript = ingestor._parse_simple_response(response)

    assert transcript.session_title == "Test Session"
    assert transcript.agenda_items
    assert transcript.agenda_items[0].speech_blocks
    assert transcript.agenda_items[0].speech_blocks[0].sentences == [
        Sentence(start_time="0m1s0ms", text="Good morning.")
    ]
