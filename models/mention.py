"""Mention model"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import TEXT, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Mention(Base):
    """Entity mention in transcript"""

    __tablename__ = "mentions"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agenda_item_index: Mapped[int | None] = mapped_column(Integer)
    speech_block_index: Mapped[int | None] = mapped_column(Integer)
    sentence_index: Mapped[int | None] = mapped_column(Integer)
    timestamp_seconds: Mapped[int | None] = mapped_column(Integer, index=True)
    context: Mapped[str | None] = mapped_column(TEXT)
    bill_id: Mapped[str | None] = mapped_column(String(100))
    speaker_id: Mapped[str | None] = mapped_column(String(100), index=True)
    speaker_canonical_id: Mapped[str | None] = mapped_column(String(100), index=True)
    agenda_title: Mapped[str | None] = mapped_column(TEXT)
    segment_id: Mapped[str | None] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "video_id": str(self.video_id),
            "agenda_item_index": self.agenda_item_index,
            "speech_block_index": self.speech_block_index,
            "sentence_index": self.sentence_index,
            "timestamp_seconds": self.timestamp_seconds,
            "context": self.context,
            "bill_id": self.bill_id,
            "speaker_id": self.speaker_id,
            "speaker_canonical_id": self.speaker_canonical_id,
            "agenda_title": self.agenda_title,
            "segment_id": self.segment_id,
        }
