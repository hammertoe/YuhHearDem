"""Mention model for entity provenance tracking."""

from datetime import datetime
from uuid import uuid4, UUID

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Mention(Base):
    """
    Entity mention with precise provenance tracking.

    Tracks every mention of an entity in the transcript with:
    - Exact sentence-level location
    - Timestamp from video
    - Context (surrounding text)
    - Session and agenda item hierarchy
    """

    __tablename__ = "mentions"

    mention_id: Mapped[UUID] = mapped_column(
        pg_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    entity_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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

    # Hierarchical location
    agenda_item_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Index of agenda item in the session",
    )
    speech_block_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Index of speech block within agenda item",
    )
    sentence_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Index of sentence within speech block",
    )

    # Timestamp and content
    timestamp: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Timestamp in XmYs format (e.g., '5m30s')",
    )
    timestamp_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Timestamp converted to seconds for sorting",
    )
    context: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="First 200 characters of the sentence for context",
    )

    # Additional metadata
    speaker_id: Mapped[str | None] = mapped_column(
        String(150),
        ForeignKey("speakers.canonical_id", ondelete="SET NULL"),
        nullable=True,
        comment="Speaker who mentioned this entity",
    )
    mention_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="direct",
        comment="Type of mention: direct, alias, pronoun_reference",
    )
    meta_data: Mapped[dict | None] = mapped_column(
        JSON,
        comment="Additional metadata about the mention",
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_mentions_entity_session",
            "entity_id",
            "session_id",
        ),
        Index(
            "ix_mentions_video_time",
            "video_id",
            "timestamp_seconds",
        ),
        Index(
            "ix_mentions_location",
            "session_id",
            "agenda_item_index",
            "speech_block_index",
            "sentence_index",
        ),
    )
