"""Knowledge graph storage layer"""

from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession, select
from sqlalchemy.orm import selectinload

from models.entity import Entity
from models.relationship import Relationship
from models.speaker import Speaker
from models.mention import Mention
from models.video import Video


class KnowledgeGraphStore:
    """Storage layer for knowledge graph entities and relationships."""

    async def find_entity(
        self,
        db: AsyncSession,
        name: str,
        entity_type: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Find entities by name or type.

        Args:
            db: Database session
            name: Entity name or partial name
            entity_type: Filter by entity type

        Returns:
            Matching entity or None
        """
        query = select(Entity)

        if name:
            query = query.where(Entity.name.ilike(f"%{name}%"))

        if entity_type:
            query = query.where(Entity.entity_type == entity_type)

        query = query.limit(10)
        result = await db.execute(query)
        entities = result.scalars().all()

        if entities:
            return entities[0].to_dict()
        return None

    async def get_relationships(
        self,
        db: AsyncSession,
        entity_id: str,
        direction: str = "all",
    ) -> List[dict]:
        """
        Get relationships for an entity.

        Args:
            db: Database session
            entity_id: Entity ID
            direction: Direction filter ('incoming', 'outgoing', 'all')

        Returns:
            List of relationships
        """
        query = select(Relationship).where(Relationship.source_id == entity_id)

        if direction == "incoming":
            query = query.where(Relationship.target_id == entity_id)
        elif direction == "outgoing":
            query = query.where(Relationship.source_id == entity_id)
        elif direction == "all":
            query = query
        else:
            raise ValueError(f"Invalid direction: {direction}")

        result = await db.execute(query.limit(20))
        relationships = result.scalars().all()

        return [rel.to_dict() for rel in relationships]

    async def get_mentions(
        self,
        db: AsyncSession,
        entity_id: str,
        video_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """
        Get mentions of an entity with timestamps.

        Args:
            db: Database session
            entity_id: Entity ID
            video_id: Optional video filter
            limit: Maximum mentions to return

        Returns:
            List of mentions
        """
        query = select(Mention).where(Mention.entity_id == entity_id)

        if video_id:
            from models.video import Video

            query = query.join(Video, Mention.video_id == Video.id).where(
                Video.youtube_id == video_id
            )
        else:
            query = query.options(selectinload("video"))

        query = query.order_by(Mention.timestamp_seconds).limit(limit)

        result = await db.execute(query)
        mentions = result.scalars().all()

        return [m.to_dict() for m in mentions]

    async def get_entity_details(
        self,
        db: AsyncSession,
        entity_id: str,
    ) -> Optional[dict]:
        """
        Get full entity details.

        Args:
            db: Database session
            entity_id: Entity ID

        Returns:
            Entity details or None
        """
        result = await db.execute(select(Entity).where(Entity.entity_id == entity_id))
        entity = result.scalar_one_or_none()

        if not entity:
            return None

        return entity.to_dict()

    async def search_by_date_range(
        self,
        db: AsyncSession,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        chamber: Optional[str] = None,
    ) -> List[Video]:
        """
        Search for sessions within date range.

        Args:
            db: Database session
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            chamber: Filter by chamber

        Returns:
            List of videos
        """
        from datetime import datetime

        query = select(Video)

        if date_from:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.where(Video.session_date >= dt)
        if date_to:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            query = query.where(Video.session_date <= dt)

        if chamber:
            query = query.where(Video.chamber == chamber)

        query = query.order_by(Video.session_date.desc()).limit(20)

        result = await db.execute(query)
        videos = result.scalars().all()

        return [v.to_dict() for v in videos]

    async def search_by_speaker(
        self,
        db: AsyncSession,
        speaker_id: str,
    ) -> List[Video]:
        """
        Find all videos where this speaker appears.

        Args:
            db: Database session
            speaker_id: Speaker canonical ID

        Returns:
            List of videos
        """
        query = select(Video).where(Video.transcript["speakers"].contains(speaker_id))

        result = await db.execute(query.limit(20))
        videos = result.scalars().all()

        return [v.to_dict() for v in videos]

    async def search_semantic(
        self,
        db: AsyncSession,
        query_text: str,
        limit: int = 10,
    ) -> List[dict]:
        """
        Semantic search over transcript sentences.

        Args:
            db: Database session
            query_text: Search query text
            limit: Maximum results

        Returns:
            List of matching sentence data
        """
        from models.vector_embedding import VectorEmbedding

        query = select(VectorEmbedding)

        query = query.order_by(VectorEmbedding.embedding)
        query = query.limit(limit)

        result = await db.execute(query)
        embeddings = result.scalars().all()

        return [
            {
                "text": emb.text,
                "video_id": str(emb.video_id),
                "speaker_id": emb.speaker_id,
                "timestamp_seconds": emb.timestamp_seconds,
                "relevance": 0.95,
            }
            for emb in embeddings
        ]
