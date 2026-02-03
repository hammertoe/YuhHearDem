"""Vector embedding model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey, TEXT, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector

    VECTOR = Vector
except ImportError:
    VECTOR = None

from core.database import Base


class VectorEmbedding(Base):
    """Vector embedding for semantic search"""

    __tablename__ = "vector_embeddings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    video_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    if VECTOR:
        embedding: Mapped[list] = mapped_column(VECTOR(384), nullable=False)
    else:
        embedding: Mapped[list] = mapped_column(JSON, nullable=False)
    text: Mapped[str] = mapped_column(TEXT, nullable=False)
    speaker_id: Mapped[Optional[str]] = mapped_column(
        String(100), ForeignKey("speakers.canonical_id")
    )
    timestamp_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    meta_data: Mapped[dict] = mapped_column(JSON, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
