"""Search API endpoints - hybrid vector + text search"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/", response_model=dict)
async def search(
    db: AsyncSession = Depends(get_db_session),
    query_text: str = Query(..., description="Search query", alias="query"),
    type: str | None = Query(
        "all", description="Search type: 'all', 'entities', 'transcripts', 'speakers'"
    ),
    chamber: str | None = Query(None, description="Filter by chamber"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """
    Hybrid search combining vector and full-text search.

    Args:
        db: Database session
        query: Search query text
        type: Type of search ('all', 'entities', 'transcripts', 'speakers')
        chamber: Filter by chamber
        limit: Maximum results to return

    Returns:
        Search results with mixed types
    """
    results = {
        "entities": [],
        "transcripts": [],
        "speakers": [],
        "total": 0,
    }

    if type in ["all", "entities"]:
        from sqlalchemy import select

        from models.entity import Entity

        select_stmt = select(Entity)

        if query_text:
            like_pattern = f"%{query_text}%"
            select_stmt = select_stmt.where(Entity.name.ilike(like_pattern))

        result = await db.execute(select_stmt.limit(limit))
        entities = result.scalars().all()

        results["entities"] = [
            {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "name": e.name,
                "canonical_name": e.canonical_name,
                "description": e.description,
                "importance_score": e.importance_score,
            }
            for e in entities
        ]
        results["total"] = len(entities)

    if type in ["all", "transcripts"]:
        from sqlalchemy import select

        from models.video import Video

        select_stmt = select(Video)

        if query_text:
            like_pattern = f"%{query_text}%"
            select_stmt = select_stmt.where(Video.title.ilike(like_pattern))

        if chamber:
            select_stmt = select_stmt.where(Video.chamber == chamber)

        result = await db.execute(select_stmt.limit(limit))
        videos = result.scalars().all()

        results["transcripts"] = [
            {
                "id": str(v.id),
                "title": v.title,
                "chamber": v.chamber,
                "session_date": v.session_date.isoformat() if v.session_date else None,
            }
            for v in videos
        ]

    if type in ["all", "speakers"]:
        from sqlalchemy import select

        from models.speaker import Speaker

        select_stmt = select(Speaker)

        if query_text:
            like_pattern = f"%{query_text}%"
            select_stmt = select_stmt.where(Speaker.name.ilike(like_pattern))

        if chamber:
            select_stmt = select_stmt.where(Speaker.chamber == chamber)

        result = await db.execute(select_stmt.limit(limit))
        speakers = result.scalars().all()

        results["speakers"] = [
            {
                "canonical_id": s.canonical_id,
                "name": s.name,
                "title": s.title,
                "role": s.role,
                "chamber": s.chamber,
            }
            for s in speakers
        ]

    return results


@router.get("/entities", response_model=dict)
async def search_entities(
    db: AsyncSession = Depends(get_db_session),
    query_text: str = Query(..., description="Search query", alias="query"),
    entity_type: str | None = Query(None, description="Filter by entity type"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Search for entities by name or type.

    Args:
        db: Database session
        query: Search query
        entity_type: Filter by entity type
        limit: Maximum results to return

    Returns:
        List of matching entities
    """
    from sqlalchemy import select

    from models.entity import Entity

    select_stmt = select(Entity)

    if query_text:
        like_pattern = f"%{query_text}%"
        select_stmt = select_stmt.where(Entity.name.ilike(like_pattern))

    if entity_type:
        select_stmt = select_stmt.where(Entity.entity_type == entity_type)

    result = await db.execute(select_stmt.limit(limit))
    entities = result.scalars().all()

    return {
        "entities": [
            {
                "entity_id": e.entity_id,
                "entity_type": e.entity_type,
                "name": e.name,
                "canonical_name": e.canonical_name,
                "description": e.description,
                "importance_score": e.importance_score,
            }
            for e in entities
        ],
        "total": len(entities),
    }


@router.get("/speakers", response_model=dict)
async def search_speakers(
    db: AsyncSession = Depends(get_db_session),
    query_text: str = Query(..., description="Search query", alias="query"),
    chamber: str | None = Query(None, description="Filter by chamber"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """
    Search for speakers by name.

    Args:
        db: Database session
        query: Search query
        chamber: Filter by chamber
        limit: Maximum results to return

    Returns:
        List of matching speakers
    """
    from sqlalchemy import select

    from models.speaker import Speaker

    select_stmt = select(Speaker)

    if query_text:
        like_pattern = f"%{query_text}%"
        select_stmt = select_stmt.where(Speaker.name.ilike(like_pattern))

    if chamber:
        select_stmt = select_stmt.where(Speaker.chamber == chamber)

    result = await db.execute(select_stmt.limit(limit))
    speakers = result.scalars().all()

    return {
        "speakers": [
            {
                "canonical_id": s.canonical_id,
                "name": s.name,
                "title": s.title,
                "role": s.role,
                "chamber": s.chamber,
            }
            for s in speakers
        ],
        "total": len(speakers),
    }
