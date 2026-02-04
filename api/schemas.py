"""API Pydantic schemas for request/response validation"""

from datetime import datetime
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
    sitting_number: str | None = None
    duration_seconds: int | None = None


class VideoCreate(VideoBase):
    """Video creation schema"""

    transcript: dict | None = None


class VideoResponse(VideoBase):
    """Video response schema"""

    id: UUID
    transcript_processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SpeakerBase(BaseModel):
    """Base speaker schema"""

    canonical_id: str
    name: str
    title: str | None = None
    role: str | None = None
    chamber: str | None = None


class SpeakerResponse(SpeakerBase):
    """Speaker response schema"""

    id: UUID
    aliases: list[str] = []
    pronoun: str | None = None
    gender: str | None = None
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
    aliases: list[str] = []
    description: str | None = None
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
    structured_response: dict | None = None


class MessageResponse(BaseModel):
    """Message response schema"""

    id: UUID
    session_id: UUID
    role: str
    content: str
    structured_response: dict | None = None
    created_at: datetime


class QueryRequest(BaseModel):
    """Query request schema"""

    query: str
    user_id: str
    session_id: str | None = None


class ResponseCard(BaseModel):
    """Response card for structured output"""

    summary: str
    details: str


class StructuredResponse(BaseModel):
    """Structured response for chat"""

    intro_message: str
    response_cards: list[ResponseCard]
    follow_up_suggestions: list[str]
    entities: list[dict] | None = None


class QueryResponse(BaseModel):
    """Query response schema"""

    session_id: str
    user_id: str
    message_id: str
    status: str
    message: str | None = None
    structured_response: StructuredResponse


class ErrorResponse(BaseModel):
    """Error response"""

    detail: str
    status: str = Field(default="error")
