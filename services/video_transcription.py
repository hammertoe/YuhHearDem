"""Video transcription service using Gemini"""

from pathlib import Path
from typing import Optional

from parsers.models import OrderPaper
from parsers.transcript_models import SessionTranscript
from services.gemini import GeminiClient
from services.speaker_matcher import SpeakerMatcher


class VideoTranscriptionService:
    """Service for transcribing parliamentary session videos."""

    def __init__(self, gemini_client: GeminiClient):
        """Initialize service with Gemini client."""
        self.client = gemini_client
        self.speaker_matcher = SpeakerMatcher()

    def transcribe(
        self,
        video_url: str,
        order_paper: OrderPaper,
        speaker_id_mapping: dict[str, str],
        fps: float = 0.25,
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
            fps=fps,
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
3. Timestamp format: XmYsZms (e.g., 0m5s250ms)
4. Preserve parliamentary language and formal tone"""

    def _parse_response(self, response: dict) -> SessionTranscript:
        """Parse Gemini response into SessionTranscript."""
        # Simplified parsing - in production would handle all cases
        return SessionTranscript(
            session_title=response.get("session_title", ""),
            date=response.get("date"),
            chamber=response.get("chamber", "house"),
            agenda_items=response.get("agenda_items", []),
            video_url=response.get("video_url"),
            video_title=response.get("video_title"),
        )
