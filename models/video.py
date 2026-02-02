"""Video model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import DateTime, String, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Video(Base):
    """Parliamentary session video"""

    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    youtube_id: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    youtube_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    chamber: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    session_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    sitting_number: Mapped[Optional[str]] = mapped_column(String(50))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    transcript: Mapped[dict] = mapped_column(JSON, nullable=False)
    transcript_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
