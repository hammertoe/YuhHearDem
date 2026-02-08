"""Relationship model"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, text, func
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Relationship(Base):
    """
    Knowledge graph relationship with provenance.

    Tracks relationships between entities with:
    - Evidence quote from transcript
    - Precise timestamp from video
    - Hierarchical location (session → agenda → speech → sentence)
    """

    __tablename__ = "relationships"

    relationship_id: Mapped[UUID] = mapped_column(
        pg_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Entity references
    source_entity_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship details
    relation: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Float)

    # Provenance - evidence from transcript
    evidence_quote: Mapped[str | None] = mapped_column(
        Text,
        comment="Direct quote from transcript supporting this relationship",
    )
    evidence_timestamp: Mapped[str | None] = mapped_column(
        String(20),
        comment="Timestamp in XmYs format",
    )
    evidence_timestamp_seconds: Mapped[int | None] = mapped_column(
        Integer,
        comment="Timestamp in seconds for sorting/filtering",
    )

    # Hierarchical location
    session_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("sessions.session_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    video_id: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("videos.video_id", ondelete="SET NULL"),
        nullable=True,
    )
    agenda_item_index: Mapped[int | None] = mapped_column(
        Integer,
        comment="Index of agenda item where relationship was observed",
    )
    speech_block_index: Mapped[int | None] = mapped_column(
        Integer,
        comment="Index of speech block where relationship was observed",
    )
    sentence_index: Mapped[int | None] = mapped_column(
        Integer,
        comment="Index of sentence where relationship was observed",
    )

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="extraction",
        server_default=text("'extraction'"),
        comment="How this relationship was created",
    )
    source_ref: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_relationships_provenance",
            "session_id",
            "video_id",
            "evidence_timestamp_seconds",
        ),
        Index(
            "uq_relationship_unique_per_session",
            "source_entity_id",
            "target_entity_id",
            "relation",
            "session_id",
            unique=True,
        ),
    )
