"""Video model"""

from datetime import datetime, timezone
import uuid as _uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


UUID = _uuid.UUID


class Video(Base):
    """Parliamentary session video"""

    __tablename__ = "videos"

    id: Mapped[_uuid.UUID] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="youtube")
    url: Mapped[str] = mapped_column(String, nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
