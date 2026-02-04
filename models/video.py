"""Video model"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Video(Base):
    """Parliamentary session video"""

    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    youtube_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    youtube_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    chamber: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    session_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    sitting_number: Mapped[str | None] = mapped_column(String(50))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    order_paper_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("order_papers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    transcript: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transcript_processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """Convert Video to dictionary."""
        return {
            "id": str(self.id) if self.id else None,
            "youtube_id": self.youtube_id,
            "youtube_url": self.youtube_url,
            "title": self.title,
            "chamber": self.chamber,
            "session_date": self.session_date.isoformat() if self.session_date else None,
            "sitting_number": self.sitting_number,
            "duration_seconds": self.duration_seconds,
            "transcript": self.transcript,
            "transcript_processed_at": self.transcript_processed_at.isoformat()
            if self.transcript_processed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
