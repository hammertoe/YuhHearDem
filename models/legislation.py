"""Legislation model"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, TEXT, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Legislation(Base):
    """Bill or resolution metadata"""

    __tablename__ = "legislation"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    legislation_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(50))
    sponsors: Mapped[list] = mapped_column(JSON, default=lambda: [])
    chamber: Mapped[str | None] = mapped_column(String(50))
    parliament_id: Mapped[str | None] = mapped_column(String(100))
    pdf_url: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(TEXT)
    stages: Mapped[list] = mapped_column(JSON, default=lambda: [])
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
