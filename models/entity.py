"""Entity model"""

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import TEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Entity(Base):
    """Knowledge graph entity with graph metrics"""

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
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default="unknown",
    )
    source_ref: Mapped[str | None] = mapped_column(String(200))
    speaker_canonical_id: Mapped[str | None] = mapped_column(String(100), index=True)
    legislation_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legislation.id")
    )
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    first_seen_date: Mapped[date | None] = mapped_column(Date)

    # Graph metrics (pre-computed for efficient GraphRAG)
    pagerank_score: Mapped[float | None] = mapped_column(Float, index=True)
    degree_centrality: Mapped[int | None] = mapped_column(Integer, index=True)
    betweenness_score: Mapped[float | None] = mapped_column(Float)
    relationship_count: Mapped[int | None] = mapped_column(Integer, default=0)
    in_degree: Mapped[int | None] = mapped_column(Integer, default=0)
    out_degree: Mapped[int | None] = mapped_column(Integer, default=0)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(DateTime)

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
            # Graph metrics
            "pagerank_score": self.pagerank_score,
            "degree_centrality": self.degree_centrality,
            "betweenness_score": self.betweenness_score,
            "relationship_count": self.relationship_count,
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
            "metrics_updated_at": self.metrics_updated_at.isoformat()
            if self.metrics_updated_at
            else None,
        }
