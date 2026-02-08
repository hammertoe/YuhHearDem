"""Entity model"""

from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Float, String, Text, text, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Entity(Base):
    """Knowledge graph entity with embedding support"""

    __tablename__ = "entities"

    entity_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_subtype: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list] = mapped_column(JSON, default=lambda: [])
    importance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    # Embedding for semantic similarity search
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768)
    )  # all-mpnet-base-v2 dimension
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        server_default=text("'unknown'"),
    )
    source_ref: Mapped[str | None] = mapped_column(String(100))
    meta_data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    # Index for vector similarity search
    __table_args__ = (
        Index(
            "ix_entities_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
        ),
    )
