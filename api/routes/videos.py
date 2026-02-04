"""Video management API endpoints"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import VideoCreate, VideoResponse
from app.dependencies import get_db_session
from models.video import Video

router = APIRouter(prefix="/api/videos", tags=["Videos"])


@router.get("/", response_model=list[VideoResponse])
async def list_videos(
    db: AsyncSession = Depends(get_db_session),
    chamber: str | None = Query(None, description="Filter by chamber"),
    date_from: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    List all videos with optional filters.

    Args:
        db: Database session
        chamber: Filter by chamber ('senate' or 'house')
        date_from: Start date filter
        date_to: End date filter
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Paginated list of videos
    """
    query = select(Video)

    if chamber:
        query = query.where(Video.chamber == chamber)

    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_from format") from exc
        query = query.where(Video.session_date >= dt)

    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date_to format") from exc
        query = query.where(Video.session_date <= dt)

    order_by = Video.session_date.desc()
    query = query.order_by(order_by)
    query = query.limit(per_page).offset((page - 1) * per_page)

    result = await db.execute(query)
    videos = result.scalars().all()

    return videos


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get a specific video by ID.

    Args:
        video_id: Video UUID

    Returns:
        Video details including transcript
    """
    result = await db.execute(select(Video).where(Video.id == video_id))

    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video


@router.post("/", response_model=dict, status_code=202)
async def create_video(
    video_data: VideoCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new video record for processing.

    Args:
        video_data: Video creation data

    Returns:
        Created video ID and status
    """
    video = Video(**video_data.model_dump())

    db.add(video)
    await db.commit()
    await db.refresh(video)

    return {
        "video_id": str(video.id),
        "status": "created",
        "message": "Video registered. Use transcription service to process.",
    }


@router.get("/{video_id}/transcript")
async def get_video_transcript(
    video_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get transcript for a video.

    Args:
        video_id: Video UUID

    Returns:
        Full transcript data
    """
    result = await db.execute(select(Video).where(Video.id == video_id))

    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video.transcript
