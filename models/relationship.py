"""Relationship model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TEXT
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Relationship(Base):
    """Knowledge graph relationship"""

    __tablename__ = "relationships"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    evidence: Mapped[str] = mapped_column(TEXT, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    video_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id")
    )
    timestamp_seconds: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
