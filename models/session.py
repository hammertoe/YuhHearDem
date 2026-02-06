"""Session model"""

import datetime
from datetime import date as dt_date

from sqlalchemy import Date, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Session(Base):
    """Parliamentary session"""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    date: Mapped[dt_date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sitting_number: Mapped[str] = mapped_column(String(50), nullable=False)
    chamber: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(nullable=False, server_default=func.now())
