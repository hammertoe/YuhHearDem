"""Transcript sentence model with normalized speaker and search indexes."""

from datetime import datetime
from uuid import uuid4, UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class TranscriptSentence(Base):
    """
    Full transcript sentence with normalized speaker reference.

    Stores every sentence from parliamentary videos with:
    - Complete text (not truncated)
    - Normalized speaker ID (canonical)
    - Original speaker name (as spoken)
    - Precise hierarchical location (session → agenda → speech → sentence)
    - Embedding for semantic search
    - Full-text vector for keyword search
    """

    __tablename__ = "transcript_sentences"

    sentence_id: Mapped[UUID] = mapped_column(
        pg_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # Hierarchical location (unique constraint)
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
    )
    agenda_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speech_block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Speaker (NORMALIZED)
    speaker_id: Mapped[str | None] = mapped_column(
        String(150),
        ForeignKey("speakers.canonical_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    speaker_name_original: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Name as spoken in transcript",
    )
    speaker_name_normalized: Mapped[str | None] = mapped_column(
        String(200),
        comment="Canonical name from speakers table (for query performance)",
    )

    # Content
    full_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Complete sentence text",
    )

    # Timestamp (seconds only, no "5m30s" string)
    timestamp_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Timestamp in seconds for sorting",
    )

    # Embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768),
        comment="Embedding for semantic search over transcript sentences",
    )

    # Full-text search vector for keyword search
    search_vector: Mapped[str | None] = mapped_column(
        String,
        comment="Full-text search vector for keyword queries",
    )

    # Meta
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    # Indexes
    __table_args__ = (
        Index(
            "uq_transcript_sentence_location",
            "session_id",
            "agenda_item_index",
            "speech_block_index",
            "sentence_index",
            unique=True,
        ),
        Index(
            "ix_transcript_sentences_speaker_time",
            "speaker_id",
            "timestamp_seconds",
        ),
        Index(
            "ix_transcript_sentences_video_time",
            "video_id",
            "timestamp_seconds",
        ),
        Index(
            "ix_transcript_sentences_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
        Index(
            "ix_transcript_sentences_search",
            "search_vector",
            postgresql_using="gin",
        ),
    )
