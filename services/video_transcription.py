"""Video transcription service using Gemini"""

from datetime import datetime, timezone
from typing import cast

from parsers.models import OrderPaper
from parsers.transcript_models import (
    Sentence,
    SessionTranscript,
    SpeechBlock,
    TranscriptAgendaItem,
)
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
            response_schema=self.TRANSCRIPT_SCHEMA,
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

    def _parse_response(self, response: dict[str, object]) -> SessionTranscript:
        """Parse Gemini response into SessionTranscript."""
        # Simplified parsing - in production would handle all cases
        date_value = response.get("date")
        parsed_date: datetime = datetime.now(timezone.utc).replace(tzinfo=None)
        if isinstance(date_value, str):
            try:
                parsed_date = datetime.fromisoformat(date_value)
            except ValueError:
                parsed_date = datetime.now(timezone.utc).replace(tzinfo=None)

        session_title = response.get("session_title")
        if not isinstance(session_title, str):
            session_title = ""
        session_title = cast(str, session_title)

        chamber = response.get("chamber")
        if not isinstance(chamber, str):
            chamber = "house"
        chamber = cast(str, chamber)

        agenda_items_raw = response.get("agenda_items")
        if not isinstance(agenda_items_raw, list):
            agenda_items_raw = []
        agenda_items_raw = cast(list, agenda_items_raw)

        agenda_items: list[TranscriptAgendaItem] = []
        for item in agenda_items_raw:
            if not isinstance(item, dict):
                continue
            topic_title = item.get("topic_title")
            if not isinstance(topic_title, str):
                continue

            speech_blocks_raw = item.get("speech_blocks")
            if not isinstance(speech_blocks_raw, list):
                speech_blocks_raw = []
            speech_blocks_raw = cast(list, speech_blocks_raw)

            speech_blocks: list[SpeechBlock] = []
            for block in speech_blocks_raw:
                if not isinstance(block, dict):
                    continue
                speaker_name = block.get("speaker_name")
                if not isinstance(speaker_name, str):
                    continue
                speaker_id = block.get("speaker_id")
                if not isinstance(speaker_id, str):
                    speaker_id = None

                sentences_raw = block.get("sentences")
                if not isinstance(sentences_raw, list):
                    sentences_raw = []
                sentences_raw = cast(list, sentences_raw)

                sentences: list[Sentence] = []
                for sentence in sentences_raw:
                    if not isinstance(sentence, dict):
                        continue
                    start_time = sentence.get("start_time")
                    text = sentence.get("text")
                    if not isinstance(start_time, str) or not isinstance(text, str):
                        continue
                    sentences.append(Sentence(start_time=start_time, text=text))

                speech_blocks.append(
                    SpeechBlock(
                        speaker_name=speaker_name,
                        speaker_id=speaker_id,
                        sentences=sentences,
                    )
                )

            agenda_items.append(
                TranscriptAgendaItem(
                    topic_title=topic_title,
                    speech_blocks=speech_blocks,
                    bill_id=item.get("bill_id"),
                    bill_match_confidence=item.get("bill_match_confidence"),
                )
            )

        video_url = response.get("video_url")
        if not isinstance(video_url, str):
            video_url = None
        video_url = cast(str | None, video_url)

        video_title = response.get("video_title")
        if not isinstance(video_title, str):
            video_title = None
        video_title = cast(str | None, video_title)

        return SessionTranscript(
            session_title=session_title,
            date=parsed_date,
            chamber=chamber,
            agenda_items=agenda_items,
            video_url=video_url,
            video_title=video_title,
        )
