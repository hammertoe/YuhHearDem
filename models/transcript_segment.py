"""Transcript segment model for semantic search."""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


class EmbeddingVector(TypeDecorator):
    """Dialect-aware embedding column."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if Vector and dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(384))
        if dialect.name == "sqlite":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(Text())


class TranscriptSegment(Base):
    """Transcript segment for vector search."""

    __tablename__ = "transcript_segments"

    segment_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("videos.video_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    speaker_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("speakers.speaker_id"))
    start_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    agenda_item_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("agenda_items.agenda_item_id"), nullable=True
    )
    speech_block_index: Mapped[int] = mapped_column(Integer)
    segment_index: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list | None] = mapped_column(EmbeddingVector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    embedding_version: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
