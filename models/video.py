"""Video model"""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Video(Base):
    """Parliamentary session video"""

    __tablename__ = "videos"

    id = mapped_column(func.gen_random_uuid(), primary_key=True)
    video_id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="youtube")
    url: Mapped[str] = mapped_column(String, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
