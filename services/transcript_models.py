"""Transcript data models for structured ingestion."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from core.utils import convert_time_to_seconds


@dataclass
class TranscriptSentence:
    """A single sentence with timestamp from transcript."""

    start_time: str  # Format: "5m30s", "1h15m20s"
    text: str

    @property
    def start_time_seconds(self) -> int:
        """Convert XmYs format to seconds."""
        return convert_time_to_seconds(self.start_time)


@dataclass
class TranscriptSpeechBlock:
    """Speech by a single speaker."""

    speaker_name: str
    sentences: list[TranscriptSentence] = field(default_factory=list)
    speaker_id: str | None = None  # Canonical speaker ID (set after matching)

    def get_full_text(self) -> str:
        """Get full text of speech."""
        return " ".join(s.text for s in self.sentences)


@dataclass
class TranscriptAgendaItem:
    """Agenda item with speeches."""

    topic_title: str
    speech_blocks: list[TranscriptSpeechBlock] = field(default_factory=list)
    bill_id: str | None = None
    bill_match_confidence: float | None = None

    def get_full_text(self) -> str:
        """Get full text of agenda item."""
        return "\n\n".join(
            f"{block.speaker_name}: {block.get_full_text()}" for block in self.speech_blocks
        )


@dataclass
class StructuredTranscript:
    """Complete structured transcript with provenance."""

    session_title: str
    session_date: date
    chamber: str  # "senate" or "house"
    sitting_number: str | None = None
    agenda_items: list[TranscriptAgendaItem] = field(default_factory=list)
    video_url: str | None = None
    video_title: str | None = None
    video_id: str | None = None
    raw_transcript: dict[str, Any] | None = None  # Original LLM output

    @classmethod
    def from_dict(cls, data: dict[str, Any], **kwargs) -> "StructuredTranscript":
        """Create from dictionary (e.g., LLM output)."""
        agenda_items = []
        for item_data in data.get("agenda_items", []):
            speech_blocks = []
            for block_data in item_data.get("speech_blocks", []):
                sentences = [
                    TranscriptSentence(
                        start_time=s["start_time"],
                        text=s["text"],
                    )
                    for s in block_data.get("sentences", [])
                ]
                speech_blocks.append(
                    TranscriptSpeechBlock(
                        speaker_name=block_data["speaker_name"],
                        sentences=sentences,
                    )
                )

            agenda_items.append(
                TranscriptAgendaItem(
                    topic_title=item_data["topic_title"],
                    speech_blocks=speech_blocks,
                )
            )

        return cls(
            session_title=data["session_title"],
            session_date=kwargs.get("session_date", date.today()),
            chamber=kwargs.get("chamber", "unknown"),
            sitting_number=kwargs.get("sitting_number"),
            agenda_items=agenda_items,
            video_url=kwargs.get("video_url"),
            video_title=kwargs.get("video_title"),
            video_id=kwargs.get("video_id"),
            raw_transcript=data,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_title": self.session_title,
            "session_date": self.session_date.isoformat(),
            "chamber": self.chamber,
            "sitting_number": self.sitting_number,
            "video_url": self.video_url,
            "video_title": self.video_title,
            "agenda_items": [
                {
                    "topic_title": item.topic_title,
                    "speech_blocks": [
                        {
                            "speaker_name": block.speaker_name,
                            "speaker_id": block.speaker_id,
                            "sentences": [
                                {"start_time": s.start_time, "text": s.text}
                                for s in block.sentences
                            ],
                        }
                        for block in item.speech_blocks
                    ],
                }
                for item in self.agenda_items
            ],
        }

    def get_all_sentences(self) -> list[tuple[TranscriptSentence, str, int, int]]:
        """
        Get all sentences with location info.

        Returns:
            List of (sentence, speaker_name, agenda_index, speech_index)
        """
        sentences = []
        for agenda_idx, item in enumerate(self.agenda_items):
            for speech_idx, block in enumerate(item.speech_blocks):
                for sentence in block.sentences:
                    sentences.append(
                        (
                            sentence,
                            block.speaker_name,
                            agenda_idx,
                            speech_idx,
                        )
                    )
        return sentences
