"""Speaker model"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Speaker(Base):
    """Canonical speaker database"""

    __tablename__ = "speakers"

    id: Mapped[UUID] = mapped_column(lambda: uuid4(), primary_key=True)
    canonical_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    chamber: Mapped[str | None] = mapped_column(String(50))
    pronoun: Mapped[str | None] = mapped_column(String(10))
    gender: Mapped[str | None] = mapped_column(String(20))
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: [])
    meta_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: {})
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
