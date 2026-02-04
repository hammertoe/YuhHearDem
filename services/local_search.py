"""Local search service for GraphRAG.

Implements entity-based retrieval with N-hop neighborhood expansion,
enabling precise answers to queries about specific entities.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from models.entity import Entity
from models.transcript_segment import TranscriptSegment
from services.embeddings import EmbeddingService
from services.query_entity_extractor import QueryEntityExtractor
from storage.knowledge_graph_store import KnowledgeGraphStore


@dataclass
class LocalSearchResult:
    """Result from local search."""

    segment_id: str
    text: str
    video_id: str
    video_title: str
    speaker_id: str | None
    timestamp_seconds: int | None
    relevance_score: float
    matched_entities: list[dict]
    relationship_path: list[dict]


@dataclass
class MatchedEntity:
    """Entity from query matched to KG entity."""

    query_name: str
    entity_id: str
    entity_name: str
    entity_type: str | None
    match_type: str
    match_score: float


class LocalSearch:
    """Local search for GraphRAG with entity-based retrieval."""

    def __init__(
        self,
        kg_store: KnowledgeGraphStore,
        entity_extractor: QueryEntityExtractor,
        embedding_service: EmbeddingService,
        fuzzy_threshold: int = 80,
    ):
        self.kg_store = kg_store
        self.entity_extractor = entity_extractor
        self.embedding_service = embedding_service
        self.fuzzy_threshold = fuzzy_threshold

    async def search(
        self,
        db: AsyncSession,
        query: str,
        max_hops: int = 2,
        segments_per_entity: int = 5,
        max_results: int = 10,
    ) -> list[LocalSearchResult]:
        """Execute local search for a query."""
        query_entities = self.entity_extractor.extract(query)
        if not query_entities:
            return await self._semantic_search_fallback(db, query, max_results)

        matched_entities = await self._match_entities_to_kg(db, query_entities)
        if not matched_entities:
            return await self._semantic_search_fallback(db, query, max_results)

        entity_ids = [m.entity_id for m in matched_entities]
        neighborhood = await self._expand_neighborhood(db, entity_ids, max_hops)

        all_entity_ids = set(entity_ids) | neighborhood["related_entities"]
        segments = await self._get_segments_for_entities(db, all_entity_ids, segments_per_entity)

        ranked_results = self._rerank_results(
            segments,
            matched_entities,
            neighborhood["relationships"],
        )

        return ranked_results[:max_results]

    async def _match_entities_to_kg(
        self,
        db: AsyncSession,
        query_entities: list,
    ) -> list[MatchedEntity]:
        """Match query entities to knowledge graph entities."""
        matched = []

        for qe in query_entities:
            result = await db.execute(
                select(Entity).where(
                    (Entity.name.ilike(qe.name)) | (Entity.canonical_name.ilike(qe.name))
                )
            )
            entity = result.scalar_one_or_none()

            if entity:
                matched.append(
                    MatchedEntity(
                        query_name=qe.name,
                        entity_id=entity.entity_id,
                        entity_name=entity.name,
                        entity_type=entity.entity_type,
                        match_type="exact",
                        match_score=100.0,
                    )
                )
                continue

            result = await db.execute(select(Entity))
            all_entities = result.scalars().all()

            best_match = None
            best_score = 0

            for entity in all_entities:
                candidates = [
                    entity.name,
                    entity.canonical_name,
                    *(entity.aliases or []),
                ]

                for candidate in candidates:
                    score = fuzz.ratio(qe.name.lower(), candidate.lower())
                    if score > best_score:
                        best_score = score
                        best_match = entity

            if best_match and best_score >= self.fuzzy_threshold:
                matched.append(
                    MatchedEntity(
                        query_name=qe.name,
                        entity_id=best_match.entity_id,
                        entity_name=best_match.name,
                        entity_type=best_match.entity_type,
                        match_type="fuzzy",
                        match_score=best_score,
                    )
                )

        return matched

    async def _expand_neighborhood(
        self,
        db: AsyncSession,
        entity_ids: list[str],
        max_hops: int,
    ) -> dict[str, Any]:
        """Expand N-hop neighborhood from seed entities."""
        if not entity_ids:
            return {"related_entities": set(), "relationships": []}

        entity_ids_str = ", ".join(f"'{eid}'" for eid in entity_ids)

        cte_query = f"""
        WITH RECURSIVE entity_hops AS (
            SELECT
                source_id as entity_id,
                0 as hop_count,
                source_id as path
            FROM relationships
            WHERE source_id IN ({entity_ids_str})

            UNION

            SELECT
                CASE
                    WHEN r.source_id = eh.entity_id THEN r.target_id
                    ELSE r.source_id
                END as entity_id,
                eh.hop_count + 1,
                eh.path || ' -> ' || CASE
                    WHEN r.source_id = eh.entity_id THEN r.target_id
                    ELSE r.source_id
                END
            FROM relationships r
            JOIN entity_hops eh ON (
                r.source_id = eh.entity_id OR r.target_id = eh.entity_id
            )
            WHERE eh.hop_count < {max_hops}
        )
        SELECT DISTINCT entity_id, hop_count, path
        FROM entity_hops
        ORDER BY hop_count, entity_id
        """

        result = await db.execute(text(cte_query))
        rows = result.fetchall()

        related_entities = set()
        relationships = []

        for row in rows:
            related_entities.add(row.entity_id)
            if row.hop_count > 0:
                relationships.append(
                    {
                        "entity_id": row.entity_id,
                        "hop_count": row.hop_count,
                        "path": row.path,
                    }
                )

        return {
            "related_entities": related_entities,
            "relationships": relationships,
        }

    async def _get_segments_for_entities(
        self,
        db: AsyncSession,
        entity_ids: set[str],
        limit_per_entity: int,
    ) -> list[dict]:
        """Get transcript segments mentioning the given entities."""
        if not entity_ids:
            return []

        entity_ids_list = list(entity_ids)

        from models.mention import Mention

        result = await db.execute(
            select(
                TranscriptSegment,
                Entity,
                Mention,
            )
            .join(Mention, TranscriptSegment.segment_id == Mention.segment_id)
            .join(Entity, Mention.entity_id == Entity.entity_id)
            .where(Mention.entity_id.in_(entity_ids_list))
            .order_by(TranscriptSegment.video_id, TranscriptSegment.start_time_seconds)
        )

        rows = result.all()

        segment_map: dict[str, dict] = {}

        for row in rows:
            seg_id = row.TranscriptSegment.segment_id

            if seg_id not in segment_map:
                segment_map[seg_id] = {
                    "segment": row.TranscriptSegment,
                    "entities": [],
                }

            segment_map[seg_id]["entities"].append(
                {
                    "entity_id": row.Entity.entity_id,
                    "name": row.Entity.name,
                    "type": row.Entity.entity_type,
                    "importance": row.Entity.importance_score,
                    "context": row.Mention.context,
                }
            )

        segments = []
        entity_segment_counts = dict.fromkeys(entity_ids, 0)

        for seg_id, data in segment_map.items():
            has_new_entity = False
            for entity in data["entities"]:
                eid = entity["entity_id"]
                if entity_segment_counts[eid] < limit_per_entity:
                    entity_segment_counts[eid] += 1
                    has_new_entity = True

            if has_new_entity:
                segments.append(
                    {
                        "segment_id": seg_id,
                        "text": data["segment"].text,
                        "video_id": str(data["segment"].video_id),
                        "speaker_id": data["segment"].speaker_id,
                        "timestamp_seconds": data["segment"].start_time_seconds,
                        "entities": data["entities"],
                    }
                )

        return segments

    def _rerank_results(
        self,
        segments: list[dict],
        matched_entities: list[MatchedEntity],
        relationships: list[dict],
    ) -> list[LocalSearchResult]:
        """Rerank segments using multiple signals."""
        results = []

        rel_map = {r["entity_id"]: r for r in relationships}

        for seg in segments:
            max_importance = max(
                (e.get("importance", 0.5) for e in seg["entities"]),
                default=0.5,
            )

            avg_match_score = sum(m.match_score for m in matched_entities) / len(matched_entities)
            match_confidence = avg_match_score / 100.0

            min_hops = min(
                (rel_map.get(e["entity_id"], {}).get("hop_count", 0) for e in seg["entities"]),
                default=0,
            )
            proximity = 1.0 / (1 + min_hops)

            score = max_importance * match_confidence * proximity

            path_info = []
            for entity in seg["entities"]:
                if entity["entity_id"] in rel_map:
                    path_info.append(rel_map[entity["entity_id"]])

            results.append(
                LocalSearchResult(
                    segment_id=seg["segment_id"],
                    text=seg["text"],
                    video_id=seg["video_id"],
                    video_title="",  # Will be filled later
                    speaker_id=seg["speaker_id"],
                    timestamp_seconds=seg["timestamp_seconds"],
                    relevance_score=score,
                    matched_entities=seg["entities"],
                    relationship_path=path_info,
                )
            )

        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    async def _semantic_search_fallback(
        self,
        db: AsyncSession,
        query: str,
        max_results: int,
    ) -> list[LocalSearchResult]:
        """Fallback to pure semantic search when no entities found."""
        segments = await self.kg_store.search_semantic(
            db, query, self.embedding_service, max_results
        )

        return [
            LocalSearchResult(
                segment_id=seg.get("segment_id", ""),
                text=seg["text"],
                video_id=seg["video_id"],
                video_title=seg.get("video_title", "Unknown"),
                speaker_id=seg.get("speaker_id"),
                timestamp_seconds=seg.get("timestamp_seconds"),
                relevance_score=seg.get("relevance", 0.5),
                matched_entities=[],
                relationship_path=[],
            )
            for seg in segments
        ]
