"""API Pydantic schemas for request/response validation"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(default="healthy")
    database_connected: bool = False
    version: str = Field(default="0.1.0")


class VideoBase(BaseModel):
    """Base video schema"""

    youtube_id: str
    youtube_url: str
    title: str
    chamber: str
    session_date: datetime
    sitting_number: Optional[str] = None
    duration_seconds: Optional[int] = None


class VideoCreate(VideoBase):
    """Video creation schema"""

    transcript: dict


class VideoResponse(VideoBase):
    """Video response schema"""

    id: UUID
    transcript_processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SpeakerBase(BaseModel):
    """Base speaker schema"""

    canonical_id: str
    name: str
    title: Optional[str] = None
    role: Optional[str] = None
    chamber: Optional[str] = None


class SpeakerResponse(SpeakerBase):
    """Speaker response schema"""

    id: UUID
    aliases: List[str] = []
    pronoun: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EntityBase(BaseModel):
    """Base entity schema"""

    entity_id: str
    entity_type: str
    name: str
    canonical_name: str


class EntityResponse(EntityBase):
    """Entity response schema"""

    id: UUID
    aliases: List[str] = []
    description: Optional[str] = None
    importance_score: float = 0.0
    created_at: datetime
    updated_at: datetime


class SessionCreate(BaseModel):
    """Session creation schema"""

    session_id: str
    user_id: str


class SessionResponse(BaseModel):
    """Session response schema"""

    id: UUID
    session_id: str
    user_id: str
    created_at: datetime
    last_updated: datetime
    archived: bool = False


class MessageCreate(BaseModel):
    """Message creation schema"""

    session_id: UUID
    role: str
    content: str
    structured_response: Optional[dict] = None


class MessageResponse(BaseModel):
    """Message response schema"""

    id: UUID
    session_id: UUID
    role: str
    content: str
    structured_response: Optional[dict] = None
    created_at: datetime


class QueryRequest(BaseModel):
    """Query request schema"""

    query: str
    user_id: str
    session_id: Optional[str] = None


class ResponseCard(BaseModel):
    """Response card for structured output"""

    summary: str
    details: str


class StructuredResponse(BaseModel):
    """Structured response for chat"""

    intro_message: str
    response_cards: List[ResponseCard]
    follow_up_suggestions: List[str]


class QueryResponse(BaseModel):
    """Query response schema"""

    session_id: str
    user_id: str
    message_id: str
    status: str
    message: Optional[str] = None
    structured_response: StructuredResponse


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str
    status: str = Field(default="error")
