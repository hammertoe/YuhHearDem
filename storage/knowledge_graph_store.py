"""Knowledge graph storage layer"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.entity import Entity
from models.mention import Mention
from models.relationship import Relationship
from models.video import Video
from services.embeddings import EmbeddingService


class KnowledgeGraphStore:
    """Storage layer for knowledge graph entities and relationships."""

    async def find_entity(
        self,
        db: AsyncSession,
        name: str,
        entity_type: str | None = None,
    ) -> dict | None:
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
    ) -> list[dict]:
        """
        Get relationships for an entity.

        Args:
            db: Database session
            entity_id: Entity ID
            direction: Direction filter ('incoming', 'outgoing', 'all')

        Returns:
            List of relationships with direction metadata
        """
        if direction == "incoming":
            # Entity is the target (receiving end)
            query = select(Relationship).where(Relationship.target_id == entity_id)
        elif direction == "outgoing":
            # Entity is the source (origin)
            query = select(Relationship).where(Relationship.source_id == entity_id)
        elif direction == "all":
            # Both incoming and outgoing
            query = select(Relationship).where(
                (Relationship.source_id == entity_id) | (Relationship.target_id == entity_id)
            )
        else:
            raise ValueError(f"Invalid direction: {direction}")

        result = await db.execute(query.limit(20))
        relationships = result.scalars().all()

        # Add direction metadata to each relationship
        results = []
        for rel in relationships:
            rel_dict = rel.to_dict()
            if rel.source_id == entity_id:
                rel_dict["direction"] = "outgoing"
                rel_dict["connected_entity_id"] = rel.target_id
            elif rel.target_id == entity_id:
                rel_dict["direction"] = "incoming"
                rel_dict["connected_entity_id"] = rel.source_id
            else:
                rel_dict["direction"] = "unknown"
                rel_dict["connected_entity_id"] = None
            results.append(rel_dict)

        return results

    async def get_mentions(
        self,
        db: AsyncSession,
        entity_id: str,
        video_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get mentions of an entity with timestamps.

        Args:
            db: Database session
            entity_id: Entity ID
            video_id: Optional video filter
            limit: Maximum mentions to return

        Returns:
            List of mentions with youtube_id
        """
        if not entity_id:
            return []

        from models.video import Video

        query = (
            select(
                Mention,
                Video.youtube_id,
                Video.youtube_url,
                Video.title,
                Video.session_date,
            )
            .where(Mention.entity_id == entity_id)
            .join(Video, Mention.video_id == Video.id)
        )

        if video_id:
            query = query.where(Video.youtube_id == video_id)

        query = query.order_by(Mention.timestamp_seconds).limit(limit)

        result = await db.execute(query)
        rows = result.all()

        mention_dicts = []
        for mention, youtube_id, youtube_url, title, session_date in rows:
            mention_dict = mention.to_dict()
            mention_dict["youtube_id"] = youtube_id
            mention_dict["youtube_url"] = youtube_url
            mention_dict["video_title"] = title
            mention_dict["session_date"] = session_date.isoformat() if session_date else None
            mention_dicts.append(mention_dict)

        return mention_dicts

    async def get_entity_details(
        self,
        db: AsyncSession,
        entity_id: str,
    ) -> dict | None:
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
        date_from: str | None = None,
        date_to: str | None = None,
        chamber: str | None = None,
    ) -> list[dict]:
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
            try:
                dt = datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                dt = datetime.strptime(date_from, "%Y-%m-%dT%H:%M:%S")
            query = query.where(Video.session_date >= dt)
        if date_to:
            try:
                dt = datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                dt = datetime.strptime(date_to, "%Y-%m-%dT%H:%M:%S")
            query = query.where(Video.session_date <= dt)

        if chamber:
            query = query.where(Video.chamber == chamber)

        query = query.order_by(Video.session_date.desc()).limit(20)

        result = await db.execute(query)
        videos = result.scalars().all()

        return [v.to_dict() for v in videos]

    async def get_latest_session(self, db: AsyncSession, chamber: str | None = None) -> dict | None:
        """Get the most recent session and key transcript highlights."""
        query = select(Video)

        if chamber:
            query = query.where(Video.chamber == chamber)

        query = query.order_by(Video.session_date.desc()).limit(1)

        result = await db.execute(query)
        video = result.scalar_one_or_none()

        if not video:
            return None

        transcript = video.transcript or {}
        topics: list[str] = []
        quotes: list[str] = []

        for item in transcript.get("agenda_items", []):
            topic_title = item.get("topic_title")
            if topic_title:
                topics.append(topic_title)

            for block in item.get("speech_blocks", []):
                for sentence in block.get("sentences", []):
                    text = sentence.get("text")
                    if text:
                        quotes.append(text)
                    if len(quotes) >= 3:
                        break
                if len(quotes) >= 3:
                    break
            if len(quotes) >= 3:
                break

        return {
            "video_id": str(video.id),
            "youtube_url": video.youtube_url,
            "title": video.title,
            "session_date": video.session_date.isoformat() if video.session_date else None,
            "chamber": video.chamber,
            "sitting_number": video.sitting_number,
            "topics": topics,
            "quotes": quotes,
        }

    async def search_by_speaker(
        self,
        db: AsyncSession,
        speaker_id: str,
    ) -> list[dict]:
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
        embedding_service: EmbeddingService,
        limit: int = 10,
    ) -> list[dict]:
        """
        Semantic search over transcript segments using vector similarity.

        Uses pgvector's cosine distance operator (<=>) for proper vector similarity search.

        Args:
            db: Database session
            query_text: Search query text
            embedding_service: Service to generate query embeddings
            limit: Maximum results

        Returns:
            List of matching segments with relevance scores
        """
        # Generate embedding for query text
        query_embeddings = embedding_service.generate_embeddings([query_text])
        if not query_embeddings or not query_embeddings[0]:
            return []

        query_vector = query_embeddings[0]

        # Use pgvector cosine distance operator (<=>)
        # The <=> operator returns cosine distance (1 - cosine similarity)
        # Lower distance = higher similarity
        # We use 1 - distance to get similarity score (0-1 range)

        # Convert Python list to PostgreSQL array format
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        # Build query with pgvector cosine distance
        # embedding <=> query_vector gives cosine distance
        # 1 - (embedding <=> query_vector) gives cosine similarity
        stmt = text(f"""
            SELECT
                id,
                video_id,
                segment_id,
                text,
                speaker_id,
                start_time_seconds,
                end_time_seconds,
                1 - (embedding <=> '{vector_str}'::vector) as similarity
            FROM transcript_segments
            ORDER BY embedding <=> '{vector_str}'::vector
            LIMIT {limit}
        """)

        result = await db.execute(stmt)
        rows = result.fetchall()

        if not rows:
            return []

        # Fetch video titles in batch
        video_ids = [row.video_id for row in rows]
        video_result = await db.execute(select(Video).where(Video.id.in_(video_ids)))
        video_map = {v.id: v for v in video_result.scalars().all()}

        results = []
        for row in rows:
            video = video_map.get(row.video_id)
            results.append(
                {
                    "segment_id": row.segment_id,
                    "text": row.text,
                    "video_id": str(row.video_id),
                    "video_title": video.title if video else "Unknown",
                    "youtube_id": video.youtube_id if video else None,
                    "youtube_url": video.youtube_url if video else None,
                    "session_date": video.session_date.isoformat()
                    if video and video.session_date
                    else None,
                    "speaker_id": row.speaker_id,
                    "timestamp_seconds": row.start_time_seconds,
                    "relevance": float(row.similarity),
                }
            )

        return results

    async def search_semantic_with_entities(
        self,
        db: AsyncSession,
        query_text: str,
        embedding_service: EmbeddingService,
        limit: int = 10,
    ) -> list[dict]:
        """
        Semantic search that also returns entities mentioned in each segment.

        This bridges the gap between vector search and knowledge graph,
        enabling GraphRAG workflows where we can traverse from text to entities.

        Args:
            db: Database session
            query_text: Search query text
            embedding_service: Service to generate query embeddings
            limit: Maximum results

        Returns:
            List of segments with entities mentioned in each
        """
        # Get semantically similar segments
        segments = await self.search_semantic(db, query_text, embedding_service, limit)

        if not segments:
            return []

        # Get segment IDs
        segment_ids = [s["segment_id"] for s in segments]

        # Fetch all entities mentioned in these segments
        mentions_result = await db.execute(
            select(Mention, Entity)
            .join(Entity, Mention.entity_id == Entity.entity_id)
            .where(Mention.segment_id.in_(segment_ids))
        )
        mentions = mentions_result.all()

        # Group entities by segment
        segment_entities: dict[str, list[dict]] = {}
        for mention, entity in mentions:
            seg_id = mention.segment_id
            if seg_id not in segment_entities:
                segment_entities[seg_id] = []
            segment_entities[seg_id].append(
                {
                    "entity_id": entity.entity_id,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "importance_score": entity.importance_score,
                }
            )

        # Add entities to each segment
        for segment in segments:
            seg_id = segment["segment_id"]
            segment["entities"] = segment_entities.get(seg_id, [])
            segment["entity_count"] = len(segment["entities"])

        return segments

    async def get_entities_in_segment(
        self,
        db: AsyncSession,
        segment_id: str,
    ) -> list[dict]:
        """
        Get all entities mentioned in a transcript segment.

        This creates the critical bridge from text (segments) to knowledge graph (entities),
        enabling GraphRAG traversal.

        Args:
            db: Database session
            segment_id: Transcript segment ID

        Returns:
            List of entities mentioned in the segment
        """
        result = await db.execute(
            select(Entity, Mention)
            .join(Mention, Entity.entity_id == Mention.entity_id)
            .where(Mention.segment_id == segment_id)
            .order_by(Mention.timestamp_seconds)
        )

        entities = []
        for entity, mention in result.all():
            entity_dict = entity.to_dict()
            entity_dict["mention_context"] = mention.context
            entity_dict["timestamp_seconds"] = mention.timestamp_seconds
            entities.append(entity_dict)

        return entities
