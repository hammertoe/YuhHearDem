"""Relationship evidence model"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class RelationshipEvidence(Base):
    """Evidence links between relationships and transcript segments"""

    __tablename__ = "relationship_evidence"

    evidence_id: Mapped[UUID] = mapped_column(
        pg_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    relationship_id: Mapped[UUID] = mapped_column(
        pg_UUID(as_uuid=True),
        ForeignKey("relationships.relationship_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("transcript_segments.segment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False
    )
    start_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        Index(
            "ix_relationship_evidence_video_time",
            "video_id",
            "start_time_seconds",
        ),
    )
