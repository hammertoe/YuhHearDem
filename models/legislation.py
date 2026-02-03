"""Legislation model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, TEXT
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Legislation(Base):
    """Bill or resolution metadata"""

    __tablename__ = "legislation"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    legislation_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(TEXT, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    sponsors: Mapped[list] = mapped_column(JSON, default=lambda: [])
    chamber: Mapped[Optional[str]] = mapped_column(String(50))
    parliament_id: Mapped[Optional[str]] = mapped_column(String(100))
    pdf_url: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(TEXT)
    stages: Mapped[list] = mapped_column(JSON, default=lambda: [])
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
