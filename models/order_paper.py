"""Order paper model"""

from datetime import datetime
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, DateTime, JSON, ForeignKey, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, UniqueConstraint

from core.database import Base


class OrderPaper(Base):
    """Order paper metadata"""

    __tablename__ = "order_papers"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    video_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pdf_path: Mapped[str] = mapped_column(String, nullable=False)
    pdf_hash: Mapped[str] = mapped_column(String, nullable=False)
    session_title: Mapped[Optional[str]] = mapped_column(String)
    session_date: Mapped[Optional[datetime]] = mapped_column(Date)
    sitting_number: Mapped[Optional[str]] = mapped_column(String(50))
    chamber: Mapped[Optional[str]] = mapped_column(String(50))
    speakers: Mapped[list] = mapped_column(JSON, nullable=False)
    agenda_items: Mapped[list] = mapped_column(JSON, nullable=False)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("video_id", "pdf_hash", name="unique_video_pdf_hash"),
    )
