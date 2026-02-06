"""Video transcript data models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, cast


@dataclass
class Sentence:
    """Single sentence with timestamp"""

    start_time: str  # Format: "XmYsZms"
    text: str


@dataclass
class SpeechBlock:
    """Block of consecutive sentences from same speaker"""

    speaker_name: str
    speaker_id: str | None = None
    sentences: list[Sentence] = field(default_factory=list)


@dataclass
class TranscriptAgendaItem:
    """Agenda item within transcript"""

    topic_title: str
    speech_blocks: list[SpeechBlock] = field(default_factory=list)
    bill_id: str | None = None
    bill_match_confidence: float | None = None


@dataclass
class SessionTranscript:
    """Complete session transcript"""

    session_title: str
    date: datetime
    chamber: str  # 'senate' | 'house'
    agenda_items: list[TranscriptAgendaItem]
    video_url: str | None = None
    video_title: str | None = None
    video_upload_date: str | None = None


def parse_gemini_transcript_response(response: dict[str, object]) -> SessionTranscript:
    """Parse Gemini response into a SessionTranscript."""
    date_value = response.get("date")
    parsed_date: datetime = datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(date_value, str):
        try:
            parsed_date = datetime.fromisoformat(date_value)
        except ValueError:
            parsed_date = datetime.now(timezone.utc).replace(tzinfo=None)
    elif isinstance(date_value, datetime):
        parsed_date = date_value

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
    agenda_items_raw = cast(list[dict[str, Any]], agenda_items_raw)

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
        speech_blocks_raw = cast(list[dict[str, Any]], speech_blocks_raw)

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
            sentences_raw = cast(list[dict[str, Any]], sentences_raw)

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

    video_upload_date = response.get("video_upload_date")
    if not isinstance(video_upload_date, str):
        video_upload_date = None
    video_upload_date = cast(str | None, video_upload_date)

    return SessionTranscript(
        session_title=session_title,
        date=parsed_date,
        chamber=chamber,
        agenda_items=agenda_items,
        video_url=video_url,
        video_title=video_title,
        video_upload_date=video_upload_date,
    )
