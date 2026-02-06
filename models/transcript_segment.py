"""Transcript segment model for semantic search."""

from datetime import datetime, timezone
import uuid as _uuid

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from core.database import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


UUID = _uuid.UUID


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

    id: Mapped[UUID] = mapped_column(server_default="gen_random_uuid()", primary_key=True)
    segment_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
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
    speaker_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("speakers.canonical_id"), nullable=True
    )
    start_time_seconds: Mapped[int] = mapped_column(Integer)
    end_time_seconds: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    agenda_item_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("agenda_items.agenda_item_id"), nullable=True
    )
    speech_block_index: Mapped[int] = mapped_column(Integer)
    segment_index: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list] = mapped_column(Vector(384), nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(80))
    embedding_version: Mapped[str | None] = mapped_column(String(40))
    meta_data: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
