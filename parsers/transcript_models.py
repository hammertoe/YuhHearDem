"""Video transcript data models"""

from dataclasses import dataclass
from datetime import datetime


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
    sentences: list[Sentence] = None


@dataclass
class TranscriptAgendaItem:
    """Agenda item within transcript"""

    topic_title: str
    speech_blocks: list[SpeechBlock] = None
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
