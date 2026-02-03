"""Chat and query API endpoints"""

from datetime import datetime
from typing import Optional, List, Dict, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.session import Session
from models.message import Message
from models.entity import Entity
from models.relationship import Relationship
from api.schemas import (
    MessageCreate,
    MessageResponse,
    QueryRequest,
    StructuredResponse,
    ResponseCard,
    QueryResponse,
)
from app.dependencies import get_db_session, get_parliamentary_agent
from services.parliamentary_agent import ParliamentaryAgent


router = APIRouter(prefix="/api", tags=["Chat"])


@router.post("/query", response_model=QueryResponse)
async def process_query(
    query_request: dict,
    db: AsyncSession = Depends(get_db_session),
    agent: ParliamentaryAgent = Depends(get_parliamentary_agent),
):
    """
    Process a natural language query and return structured response.

    Args:
        query_request: Query data with 'query', 'user_id', 'session_id'
        db: Database session
        agent: Parliamentary agent for RAG

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

    session = None

    if session_id:
        result = await db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        session = result.scalar_one_or_none()
    else:
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
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

    session.last_updated = datetime.utcnow()
    await db.commit()

    agent_response = await agent.query(db=db, user_query=query)

    if agent_response.get("success"):
        answer = agent_response.get("answer", "")

        assistant_response = StructuredResponse(
            intro_message="Based on my analysis of parliamentary records:",
            response_cards=[
                ResponseCard(
                    summary="Analysis Complete",
                    details=answer,
                )
            ],
            follow_up_suggestions=[
                "Tell me more about this entity",
                "What legislation is related?",
                "Show me all mentions",
            ],
        )

        structured_response_dict = assistant_response.model_dump()
        if agent_response.get("entities"):
            structured_response_dict["entities"] = agent_response["entities"]

    else:
        assistant_response = StructuredResponse(
            intro_message="I encountered an issue while processing your query:",
            response_cards=[
                ResponseCard(
                    summary="Error",
                    details=agent_response.get("error", "Unknown error"),
                )
            ],
            follow_up_suggestions=[
                "Try rephrasing your question",
                "Search for a specific topic",
                "Browse recent sessions",
            ],
        )
        structured_response_dict = assistant_response.model_dump()

    assistant_message = Message(
        session_id=session.id,
        role="assistant",
        content="",
        structured_response=assistant_response.model_dump(),
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return QueryResponse(
        session_id=session.session_id,
        user_id=user_id,
        message_id=str(assistant_message.id),
        status="success",
        structured_response=assistant_response,
    )


@router.post("/query/stream", response_class=StreamingResponse)
async def process_query_stream(
    query_request: dict,
    db: AsyncSession = Depends(get_db_session),
    agent: ParliamentaryAgent = Depends(get_parliamentary_agent),
):
    """
    Process a natural language query with streaming response.

    Args:
        query_request: Query data with 'query', 'user_id', 'session_id'
        db: Database session
        agent: Parliamentary agent for RAG

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

    session = None

    if session_id:
        result = await db.execute(
            select(Session).where(Session.session_id == session_id)
        )
        session = result.scalar_one_or_none()
    else:
        import uuid

        session = Session(
            session_id=f"session_{str(uuid.uuid4())[:8]}",
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

    session.last_updated = datetime.utcnow()
    await db.commit()

    async def event_generator():
        import json

        yield f"event: thinking\n"
        yield f"data: {json.dumps({'status': 'thinking'})}\n\n"

        agent_response = await agent.query(db=db, user_query=query)

        if agent_response.get("success"):
            answer = agent_response.get("answer", "")

            assistant_response = StructuredResponse(
                intro_message="Based on my analysis of the parliamentary records:",
                response_cards=[
                    ResponseCard(
                        summary="Analysis Complete",
                        details=answer,
                    )
                ],
                follow_up_suggestions=[
                    "Tell me more about this entity",
                    "What legislation is related?",
                    "Show me all mentions",
                ],
            )
        else:
            assistant_response = StructuredResponse(
                intro_message="I encountered an issue while processing your query:",
                response_cards=[
                    ResponseCard(
                        summary="Error",
                        details=agent_response.get("error", "Unknown error"),
                    )
                ],
                follow_up_suggestions=[
                    "Try rephrasing your question",
                    "Search for a specific topic",
                    "Browse recent sessions",
                ],
            )

        assistant_message = Message(
            session_id=session.id,
            role="assistant",
            content="",
            structured_response=assistant_response.model_dump(),
        )
        db.add(assistant_message)
        await db.commit()
        await db.refresh(assistant_message)

        response_json = json.dumps(
            {
                "session_id": session.session_id,
                "user_id": user_id,
                "message_id": str(assistant_message.id),
                "status": "success",
                "structured_response": assistant_response.model_dump(),
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
        db: Database session

    Returns:
        Session information
    """
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

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
        db: Database session

    Returns:
        List of messages
    """
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
        db: Database session

    Returns:
        Success message
    """
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


@router.get("/session/{session_id}/graph", response_model=dict)
async def get_session_graph(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get knowledge graph for a session's entities and relationships.

    Args:
        session_id: Session UUID string
        db: Database session

    Returns:
        Nodes and edges for graph visualization
    """
    from sqlalchemy import func

    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all messages for this session
    result = await db.execute(select(Message).where(Message.session_id == session.id))
    messages = result.scalars().all()

    # Extract entity IDs from message structured responses
    entity_ids: Set[str] = set()
    for message in messages:
        if message.structured_response:
            response = message.structured_response
            if response.get("entities"):
                for entity in response["entities"]:
                    entity_ids.add(entity.get("entity_id"))

    # Get entity details
    nodes = []
    if entity_ids:
        result = await db.execute(
            select(Entity).where(Entity.entity_id.in_(entity_ids))
        )
        entities = result.scalars().all()

        nodes = [
            {
                "id": entity.entity_id,
                "label": entity.name,
                "type": entity.entity_type,
                "metadata": {
                    "description": entity.description,
                    "importance_score": entity.importance_score,
                },
            }
            for entity in entities
        ]

    # Get relationships between these entities
    relationships = []
    if entity_ids:
        result = await db.execute(
            select(Relationship).where(
                or_(
                    Relationship.source_id.in_(entity_ids),
                    Relationship.target_id.in_(entity_ids),
                )
            )
        )
        rels = result.scalars().all()

        relationships = [
            {
                "source": rel.source_id,
                "target": rel.target_id,
                "relation": rel.relation_type,
                "sentiment": rel.sentiment,
                "evidence": rel.evidence,
            }
            for rel in rels
        ]

    return {
        "nodes": nodes,
        "edges": relationships,
    }
