"""Speaker model"""

from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Speaker(Base):
    """Canonical speaker database"""

    __tablename__ = "speakers"

    speaker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    chamber: Mapped[str | None] = mapped_column(String(50))
    aliases: Mapped[list] = mapped_column(JSON, default=lambda: [])
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default="now()")
