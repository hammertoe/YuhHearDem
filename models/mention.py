"""Mention model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, TEXT, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Mention(Base):
    """Entity mention in transcript"""

    __tablename__ = "mentions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
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
    agenda_item_index: Mapped[Optional[int]] = mapped_column(Integer)
    sentence_index: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp_seconds: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    context: Mapped[Optional[str]] = mapped_column(TEXT)
    bill_id: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
