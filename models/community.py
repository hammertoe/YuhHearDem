"""Community models for GraphRAG."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class EntityCommunity(Base):
    """Links entities to their community memberships (Leiden algorithm output)."""

    __tablename__ = "entity_communities"

    entity_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("entities.entity_id", ondelete="CASCADE"),
        primary_key=True,
    )
    community_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    community_level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "community_id": self.community_id,
            "community_level": self.community_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunitySummary(Base):
    """Pre-computed summaries for each community."""

    __tablename__ = "community_summaries"

    community_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_entities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_dict(self) -> dict:
        return {
            "community_id": self.community_id,
            "summary": self.summary,
            "key_entities": self.key_entities,
            "member_count": self.member_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
