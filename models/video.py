"""Video model"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Video(Base):
    """Parliamentary session video"""

    __tablename__ = "videos"

    id: Mapped[UUID] = mapped_column(pg_UUID(as_uuid=True), primary_key=True, default=uuid4)
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
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
