"""Transcript segment model for semantic search."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, TEXT, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

try:
    from pgvector.sqlalchemy import Vector

    VECTOR = Vector
except ImportError:
    VECTOR = None


class TranscriptSegment(Base):
    """Transcript segment for vector search."""

    __tablename__ = "transcript_segments"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    video_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    agenda_item_index: Mapped[int | None] = mapped_column(Integer)
    speech_block_index: Mapped[int | None] = mapped_column(Integer)
    segment_index: Mapped[int | None] = mapped_column(Integer)
    start_time_seconds: Mapped[int | None] = mapped_column(Integer)
    end_time_seconds: Mapped[int | None] = mapped_column(Integer)
    speaker_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("speakers.canonical_id"))
    text: Mapped[str] = mapped_column(TEXT, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    embedding_version: Mapped[str | None] = mapped_column(String(40))
    if VECTOR:
        embedding: Mapped[list] = mapped_column(VECTOR(768), nullable=False)
    else:
        embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
