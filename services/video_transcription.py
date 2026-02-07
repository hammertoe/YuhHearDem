"""Video transcription service using Gemini"""

from parsers.models import OrderPaper
from parsers.transcript_models import SessionTranscript, parse_gemini_transcript_response
from services.gemini import GeminiClient
from services.speaker_matcher import SpeakerMatcher


class VideoTranscriptionService:
    """Service for transcribing parliamentary session videos."""

    TRANSCRIPT_SCHEMA = {
        "type": "object",
        "properties": {
            "session_title": {"type": "string"},
            "date": {"type": "string"},
            "chamber": {"type": "string"},
            "video_url": {"type": "string"},
            "video_title": {"type": "string"},
            "agenda_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic_title": {"type": "string"},
                        "bill_id": {"type": "string"},
                        "speech_blocks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "speaker_name": {"type": "string"},
                                    "speaker_id": {"type": "string"},
                                    "sentences": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "start_time": {"type": "string"},
                                                "text": {"type": "string"},
                                            },
                                            "required": ["start_time", "text"],
                                        },
                                    },
                                },
                                "required": ["speaker_name", "sentences"],
                            },
                        },
                    },
                    "required": ["topic_title", "speech_blocks"],
                },
            },
        },
        "required": ["session_title", "agenda_items"],
    }

    def __init__(self, gemini_client: GeminiClient) -> None:
        """Initialize service with Gemini client."""
        self.client = gemini_client
        self.speaker_matcher = SpeakerMatcher()

    def transcribe(
        self,
        video_url: str,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
        fps: float = 0.25,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> SessionTranscript:
        """
        Transcribe a video with order paper context.

        Args:
            video_url: YouTube URL
            order_paper: Parsed order paper
            speaker_id_mapping: Known speaker IDs
            fps: Frames per second

        Returns:
            SessionTranscript object
        """
        prompt = self._build_transcription_prompt(order_paper, speaker_id_mapping)

        response = self.client.analyze_video_with_transcript(
            video_url=video_url,
            prompt=prompt,
            response_schema=self.TRANSCRIPT_SCHEMA,
            fps=fps,
            start_time=start_time,
            end_time=end_time,
        )

        return self._parse_response(response)

    def _build_transcription_prompt(
        self,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
    ) -> str:
        """Build transcription prompt with order paper context."""
        speaker_list = []
        for speaker in order_paper.speakers or []:
            canonical_id = speaker_id_mapping.get(speaker.name, speaker.name)
            info = f"ID: {canonical_id}, Name: {speaker.name}"
            if speaker.role:
                info += f", Role: {speaker.role}"
            speaker_list.append(f"  - {info}")

        agenda_list = []
        for i, item in enumerate(order_paper.agenda_items or [], 1):
            agenda_list.append(f"  {i}. {item.topic_title}")
            if item.primary_speaker:
                agenda_list.append(f"     Speaker: {item.primary_speaker}")

        return f"""Transcribe this Barbados parliamentary session with precise speaker attribution.

SESSION CONTEXT:
- Title: {order_paper.session_title}
- Date: {order_paper.session_date}

SPEAKERS (for speaker identification):
{chr(10).join(speaker_list)}

AGENDA (expected structure):
{chr(10).join(agenda_list)}

 TRANSCRIPTION INSTRUCTIONS:
1. Structure by agenda items above
2. For each speech block, provide:
   - speaker_name: Name as spoken (exact wording with titles)
   - speaker_id: Use exact ID from speaker list
   - sentences: List of sentences with timestamps

TIMESTAMP FORMAT - CRITICAL REQUIREMENT:
ALL timestamps MUST use this EXACT format: XmYsZms (minutes, seconds, milliseconds)
- Examples: 0m0s0ms, 2m34s500ms, 45m10s100ms
- NEVER use: "0:00", "00:00:00", PT0S, or any other format
- Each sentence MUST have a timestamp

4. Preserve parliamentary language and formal tone
5. ENSURE CORRECT TIMESTAMP FORMAT FOR EVERY SENTENCE"""

    def _parse_response(self, response: dict[str, object]) -> SessionTranscript:
        """Parse Gemini response into SessionTranscript."""
        return parse_gemini_transcript_response(response)
