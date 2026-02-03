"""Session model"""

from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Session(Base):
    """User chat session"""

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
