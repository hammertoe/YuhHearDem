"""Entity model"""

from datetime import datetime, date
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, Float, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, TEXT
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Entity(Base):
    """Knowledge graph entity"""

    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    entity_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    canonical_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=lambda: [])
    description: Mapped[Optional[str]] = mapped_column(TEXT)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    legislation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legislation.id")
    )
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    first_seen_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
