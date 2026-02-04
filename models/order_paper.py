"""Order paper model"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Date, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class OrderPaper(Base):
    """Order paper metadata"""

    __tablename__ = "order_papers"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pdf_path: Mapped[str] = mapped_column(String, nullable=False)
    pdf_hash: Mapped[str] = mapped_column(String, nullable=False)
    session_title: Mapped[str | None] = mapped_column(String)
    session_date: Mapped[datetime | None] = mapped_column(Date)
    sitting_number: Mapped[str | None] = mapped_column(String(50))
    chamber: Mapped[str | None] = mapped_column(String(50))
    speakers: Mapped[list] = mapped_column(JSON, nullable=False)
    agenda_items: Mapped[list] = mapped_column(JSON, nullable=False)
    parsed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
