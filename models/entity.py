"""Entity model"""

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import TEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Entity(Base):
    """Knowledge graph entity"""

    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    entity_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_subtype: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(TEXT, nullable=False)
    canonical_name: Mapped[str] = mapped_column(TEXT, nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=lambda: [])
    description: Mapped[str | None] = mapped_column(TEXT)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    entity_confidence: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(50))
    source_ref: Mapped[str | None] = mapped_column(String(200))
    speaker_canonical_id: Mapped[str | None] = mapped_column(String(100), index=True)
    legislation_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legislation.id")
    )
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    first_seen_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_subtype": self.entity_subtype,
            "name": self.name,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "description": self.description,
            "importance_score": self.importance_score,
            "entity_confidence": self.entity_confidence,
            "source": self.source,
            "source_ref": self.source_ref,
            "speaker_canonical_id": self.speaker_canonical_id,
            "first_seen_date": self.first_seen_date.isoformat() if self.first_seen_date else None,
        }
