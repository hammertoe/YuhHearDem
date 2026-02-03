"""Order paper data models"""

from dataclasses import dataclass
from datetime import date


@dataclass
class OrderPaperSpeaker:
    """Speaker from order paper"""

    name: str
    title: str | None = None
    role: str | None = None


@dataclass
class AgendaItem:
    """Agenda item from order paper"""

    topic_title: str
    primary_speaker: str | None = None
    description: str | None = None


@dataclass
class OrderPaper:
    """Parsed order paper"""

    session_title: str
    session_date: date
    sitting_number: str | None = None
    speakers: list[OrderPaperSpeaker] = None
    agenda_items: list[AgendaItem] = None
