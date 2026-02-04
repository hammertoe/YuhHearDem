"""Global search service for GraphRAG."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.community import CommunitySummary, EntityCommunity
from models.entity import Entity
from models.mention import Mention
from models.transcript_segment import TranscriptSegment
from models.video import Video
from services.embeddings import EmbeddingService


@dataclass
class GlobalSearchResult:
    """Result from global search."""

    community_id: int
    community_summary: str
    primary_focus: str
    relevance_score: float
    member_entities: list[dict]
    representative_segments: list[dict]


class GlobalSearch:
    """Global search for GraphRAG using community summaries."""

    def __init__(self, embedding_service: EmbeddingService):
        self.embedding_service = embedding_service

    async def search(
        self,
        db: AsyncSession,
        query: str,
        max_communities: int = 3,
        segments_per_community: int = 5,
    ) -> list[GlobalSearchResult]:
        result = await db.execute(
            select(CommunitySummary).order_by(CommunitySummary.community_id)
        )
        summaries = result.scalars().all()

        if not summaries:
            return []

        ranked_communities = await self._rank_communities(query, summaries)
        top_communities = ranked_communities[:max_communities]

        results = []
        for community_data in top_communities:
            community_id = community_data["community_id"]

            member_entities = await self._get_community_members(db, community_id)
            segments = await self._get_representative_segments(
                db, community_id, segments_per_community
            )

            results.append(GlobalSearchResult(
                community_id=community_id,
                community_summary=community_data["summary"],
                primary_focus=community_data.get("primary_focus", ""),
                relevance_score=community_data["relevance_score"],
                member_entities=member_entities,
                representative_segments=segments,
            ))

        return results

    async def _rank_communities(
        self,
        query: str,
        summaries: list[CommunitySummary],
    ) -> list[dict]:
        if not summaries:
            return []

        query_embedding = self.embedding_service.generate_embeddings([query])[0]
        summary_texts = [s.summary for s in summaries]
        summary_embeddings = self.embedding_service.generate_embeddings(summary_texts)

        import math

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)

        scored = []
        for summary, embedding in zip(summaries, summary_embeddings):
            similarity = cosine_similarity(query_embedding, embedding)
            scored.append({
                "community_id": summary.community_id,
                "summary": summary.summary,
                "primary_focus": summary.key_entities[0] if summary.key_entities else "",
                "relevance_score": similarity,
                "member_count": summary.member_count,
            })

        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored

    async def _get_community_members(
        self,
        db: AsyncSession,
        community_id: int,
        limit: int = 20,
    ) -> list[dict]:
        result = await db.execute(
            select(Entity)
            .join(EntityCommunity, Entity.entity_id == EntityCommunity.entity_id)
            .where(EntityCommunity.community_id == community_id)
            .order_by(Entity.importance_score.desc())
            .limit(limit)
        )
        entities = result.scalars().all()

        return [
            {
                "entity_id": e.entity_id,
                "name": e.name,
                "type": e.entity_type,
                "importance": e.importance_score,
            }
            for e in entities
        ]

    async def _get_representative_segments(
        self,
        db: AsyncSession,
        community_id: int,
        limit: int = 5,
    ) -> list[dict]:
        result = await db.execute(
            select(EntityCommunity.entity_id)
            .where(EntityCommunity.community_id == community_id)
        )
        entity_ids = [row[0] for row in result.all()]

        if not entity_ids:
            return []

        result = await db.execute(
            select(
                TranscriptSegment,
                Video,
                Mention,
            )
            .join(Mention, TranscriptSegment.segment_id == Mention.segment_id)
            .join(Video, TranscriptSegment.video_id == Video.id)
            .where(Mention.entity_id.in_(entity_ids))
            .order_by(TranscriptSegment.video_id, TranscriptSegment.start_time_seconds)
            .limit(limit * 3)
        )

        rows = result.all()

        segment_scores: dict[str, dict] = {}
        for row in rows:
            seg_id = row.TranscriptSegment.segment_id
            if seg_id not in segment_scores:
                segment_scores[seg_id] = {
                    "segment": row.TranscriptSegment,
                    "video": row.Video,
                    "entity_count": 0,
                    "entities": set(),
                }
            segment_scores[seg_id]["entities"].add(row.Mention.entity_id)
            segment_scores[seg_id]["entity_count"] = len(segment_scores[seg_id]["entities"])

        sorted_segments = sorted(
            segment_scores.values(),
            key=lambda x: x["entity_count"],
            reverse=True,
        )[:limit]

        return [
            {
                "segment_id": s["segment"].segment_id,
                "text": s["segment"].text,
                "video_id": str(s["segment"].video_id),
                "video_title": s["video"].title,
                "speaker_id": s["segment"].speaker_id,
                "timestamp_seconds": s["segment"].start_time_seconds,
                "entity_count": s["entity_count"],
            }
            for s in sorted_segments
        ]
