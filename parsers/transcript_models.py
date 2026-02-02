"""Video transcript data models"""

from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Sentence:
    """Single sentence with timestamp"""
    start_time: str  # Format: "XmYsZms"
    text: str


@dataclass
class SpeechBlock:
    """Block of consecutive sentences from same speaker"""
    speaker_name: str
    speaker_id: Optional[str] = None
    sentences: List[Sentence] = None


@dataclass
class TranscriptAgendaItem:
    """Agenda item within transcript"""
    topic_title: str
    speech_blocks: List[SpeechBlock] = None
    bill_id: Optional[str] = None
    bill_match_confidence: Optional[float] = None


@dataclass
class SessionTranscript:
    """Complete session transcript"""
    session_title: str
    date: datetime
    chamber: str  # 'senate' | 'house'
    agenda_items: List[TranscriptAgendaItem]
    video_url: Optional[str] = None
    video_title: Optional[str] = None
    video_upload_date: Optional[str] = None
