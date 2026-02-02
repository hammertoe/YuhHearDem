"""Order paper data models"""

from datetime import date
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class OrderPaperSpeaker:
    """Speaker from order paper"""

    name: str
    title: Optional[str] = None
    role: Optional[str] = None


@dataclass
class AgendaItem:
    """Agenda item from order paper"""

    topic_title: str
    primary_speaker: Optional[str] = None
    description: Optional[str] = None


@dataclass
class OrderPaper:
    """Parsed order paper"""

    session_title: str
    session_date: date
    sitting_number: Optional[str] = None
    speakers: List[OrderPaperSpeaker] = None
    agenda_items: List[AgendaItem] = None
