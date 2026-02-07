"""Order paper model for database storage"""

from datetime import date, datetime

from sqlalchemy import JSON, Column, Date, DateTime, Integer, String, Text

from core.database import Base


class OrderPaper(Base):
    """Order paper from parliamentary sessions"""

    __tablename__ = "order_papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_paper_id = Column(String(100), unique=True, nullable=False, index=True)
    session_title = Column(String(500), nullable=False)
    session_date = Column(Date, nullable=False, index=True)
    sitting_number = Column(String(100), nullable=True)
    chamber = Column(String(50), nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=True)  # 'pdf', 'web', etc.
    speakers = Column(JSON, default=list)  # List of speaker dicts
    agenda_items = Column(JSON, default=list)  # List of agenda item dicts
    raw_content = Column(Text, nullable=True)  # Original PDF text if available
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<OrderPaper({self.order_paper_id}, {self.session_date}, {self.chamber})>"
