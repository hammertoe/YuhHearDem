"""Chat and query API endpoints"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from models.session import Session
from models.message import Message
from api.schemas import MessageCreate, MessageResponse
from app.dependencies import get_db_session


router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/query", response_model=dict)
async def process_query(
    query_request: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Process a natural language query and return structured response.

    Args:
        query_request: Query data with 'query', 'user_id', 'session_id'
        db: Database session

    Returns:
        Structured response with session info
    """
    query = query_request.get("query", "")
    user_id = query_request.get("user_id")
    session_id = query_request.get("session_id")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    from sqlalchemy import select
    from models.session import Session

    session = None

    if session_id:
        result = await db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        session = result.scalar_one_or_none()
    else:
        session = Session(
            session_id=f"session_{user_id[:8]}",
            user_id=user_id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    user_message = Message(
        session_id=session.id,
        role="user",
        content=query,
    )
    db.add(user_message)
    await db.commit()

    await db.execute(select(Session).where(Session.id == session.id))
    session.last_updated = datetime.utcnow()
    await db.commit()

    assistant_response = {
        "intro_message": "I'm analyzing the parliamentary records to answer your question. This feature is being enhanced.",
        "response_cards": [
            {
                "summary": "Search functionality available",
                "details": f"You asked: '{query}'. The system is currently being enhanced to provide detailed parliamentary information with source citations. This will include entity extraction, relationships, and semantic search capabilities.",
            }
        ],
        "follow_up_suggestions": [
            "What legislation has been discussed recently?",
            "Who spoke about this topic?",
            "Show me recent sessions from the Senate",
        ],
    }

    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content="",
        structured_response=assistant_response,
    )
    db.add(assistant_message)
    await db.commit()

    return {
        "session_id": session.session_id,
        "user_id": user_id,
        "message_id": str(assistant_message.id),
        "status": "success",
        "structured_response": assistant_response,
    }


@router.post("/query/stream", response_class=StreamingResponse)
async def process_query_stream(
    query_request: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Process a natural language query with streaming response.

    Args:
        query_request: Query data with 'query', 'user_id', 'session_id'
        db: Database session

    Returns:
        Server-Sent Events stream
    """
    query = query_request.get("query", "")
    user_id = query_request.get("user_id")
    session_id = query_request.get("session_id")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    from sqlalchemy import select
    from models.session import Session

    session = None

    if session_id:
        result = await db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        session = result.scalar_one_or_none()
    else:
        session = Session(
            session_id=f"session_{user_id[:8]}",
            user_id=user_id,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    user_message = Message(
        session_id=session.id,
        role="user",
        content=query,
    )
    db.add(user_message)
    await db.commit()

    await db.execute(select(Session).where(Session.id == session.id))
    session.last_updated = datetime.utcnow()
    await db.commit()

    async def event_generator():
        yield f"event: thinking\n"
        import json

        assistant_response = {
            "intro_message": "I'm analyzing the parliamentary records to answer your question.",
            "response_cards": [
                {
                    "summary": "Search functionality available",
                    "details": f"You asked: '{query}'. The system is being enhanced with entity extraction and semantic search capabilities.",
                }
            ],
            "follow_up_suggestions": [
                "What legislation has been discussed recently?",
                "Show me recent sessions from the Senate",
            ],
        }
        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content="",
            structured_response=assistant_response,
        )
        db.add(assistant_message)
        await db.commit()

        response_json = json.dumps(
            {
                "session_id": session.session_id,
                "user_id": user_id,
                "message_id": str(assistant_message.id),
                "status": "success",
                "structured_response": assistant_response,
            }
        )
        yield f"event: response\n"
        yield f"data: {response_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/session/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get session details.

    Args:
        session_id: Session UUID string

    Returns:
        Session information
    """
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from sqlalchemy import select, func
    from models.message import Message

    result = await db.execute(select(Message).where(Message.session_id == session.id))
    messages = result.scalars().all()

    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_updated": session.last_updated.isoformat()
        if session.last_updated
        else None,
        "archived": session.archived,
        "message_count": len(messages),
    }


@router.get("/session/{session_id}/messages", response_model=dict)
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all messages for a session.

    Args:
        session_id: Session UUID string

    Returns:
        List of messages
    """
    from sqlalchemy import select
    from models.session import Session
    from models.message import Message

    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    return {
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "structured_response": m.structured_response,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/session/{session_id}/archive", response_model=dict)
async def archive_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Archive a session.

    Args:
        session_id: Session UUID string

    Returns:
        Success message
    """
    from sqlalchemy import select, update
    from models.session import Session

    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.archived:
        raise HTTPException(status_code=400, detail="Session already archived")

    session.archived = True
    await db.commit()

    return {
        "status": "success",
        "message": "Session archived",
    }
