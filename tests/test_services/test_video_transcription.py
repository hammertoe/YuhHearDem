"""Video transcription service tests"""

from datetime import date
from unittest.mock import Mock

from parsers.models import OrderPaper
from parsers.transcript_models import Sentence, SpeechBlock, TranscriptAgendaItem
from services.video_transcription import VideoTranscriptionService


class TestVideoTranscriptionService:
    """Test video transcription service."""

    def test_initialization(self):
        """Test service initialization."""
        mock_client = Mock()
        service = VideoTranscriptionService(mock_client)

        assert service.client == mock_client
        assert service.speaker_matcher is not None

    def test_build_transcription_prompt(self):
        """Test prompt building."""
        mock_client = Mock()
        service = VideoTranscriptionService(mock_client)

        order_paper = OrderPaper(
            session_title="Test Session",
            session_date=date(2024, 1, 1),
            speakers=[],
            agenda_items=[],
        )

        prompt = service._build_transcription_prompt(order_paper, {})

        assert "Test Session" in prompt
        assert "2024-01-01" in prompt
        assert "SPEAKERS" in prompt
        assert "AGENDA" in prompt

    def test_parse_response(self):
        """Test response parsing."""
        mock_client = Mock()
        service = VideoTranscriptionService(mock_client)

        response = {
            "session_title": "Test Session",
            "date": "2024-01-01",
            "chamber": "senate",
            "agenda_items": [],
            "video_url": "https://example.com",
        }

        transcript = service._parse_response(response)

        assert transcript.session_title == "Test Session"
        assert transcript.chamber == "senate"
        assert transcript.video_url == "https://example.com"

    def test_transcribe_passes_response_schema(self):
        """Transcribe should request structured JSON output."""
        mock_client = Mock()
        mock_client.analyze_video_with_transcript = Mock(
            return_value={
                "session_title": "Test Session",
                "date": "2024-01-01",
                "chamber": "house",
                "agenda_items": [],
            }
        )
        service = VideoTranscriptionService(mock_client)

        order_paper = OrderPaper(
            session_title="Test Session",
            session_date=date(2024, 1, 1),
            speakers=[],
            agenda_items=[],
        )

        service.transcribe(
            video_url="https://example.com",
            order_paper=order_paper,
            speaker_id_mapping={},
        )

        _, kwargs = mock_client.analyze_video_with_transcript.call_args

        assert kwargs["response_schema"] == service.TRANSCRIPT_SCHEMA

    def test_parse_response_builds_transcript_objects(self):
        """Agenda items and speech blocks should be dataclasses."""
        mock_client = Mock()
        service = VideoTranscriptionService(mock_client)

        response = {
            "session_title": "Test Session",
            "date": "2024-01-01",
            "chamber": "house",
            "agenda_items": [
                {
                    "topic_title": "Opening",
                    "speech_blocks": [
                        {
                            "speaker_name": "Hon. Jane Doe",
                            "speaker_id": "speaker-1",
                            "sentences": [{"start_time": "0m0s0ms", "text": "Welcome."}],
                        }
                    ],
                }
            ],
        }

        transcript = service._parse_response(response)

        assert isinstance(transcript.agenda_items[0], TranscriptAgendaItem)
        assert isinstance(transcript.agenda_items[0].speech_blocks[0], SpeechBlock)
        assert isinstance(transcript.agenda_items[0].speech_blocks[0].sentences[0], Sentence)
