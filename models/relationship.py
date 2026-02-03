"""Relationship model"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import TEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Relationship(Base):
    """Knowledge graph relationship"""

    __tablename__ = "relationships"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    evidence: Mapped[str] = mapped_column(TEXT, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(50))
    source_ref: Mapped[str | None] = mapped_column(String(200))
    video_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id"))
    timestamp_seconds: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "sentiment": self.sentiment,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "timestamp_seconds": self.timestamp_seconds,
            "source": self.source,
            "source_ref": self.source_ref,
        }
