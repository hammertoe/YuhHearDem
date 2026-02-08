"""Speaker model"""

from datetime import datetime, timezone
from sqlalchemy import func, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as pg_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Speaker(Base):
    """Canonical speaker database with deduplication support"""

    __tablename__ = "speakers"

    id = mapped_column(pg_UUID, server_default=func.gen_random_uuid(), primary_key=True)
    canonical_id: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(200))
    party: Mapped[str | None] = mapped_column(String(100))
    chamber: Mapped[str | None] = mapped_column(String(50))
    pronouns: Mapped[str | None] = mapped_column(String(20))
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=[])
    # Track which sessions this speaker appeared in
    session_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=[])
    # Metadata for extensibility
    meta_data: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
