"""Hybrid GraphRAG search - single unified approach."""

from dataclasses import dataclass, field
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.entity import Entity
from models.relationship import Relationship
from models.transcript_segment import TranscriptSegment
from models.video import Video
from services.embeddings import EmbeddingService
from services.query_entity_extractor import QueryEntityExtractor
from storage.knowledge_graph_store import KnowledgeGraphStore


@dataclass
class GraphContext:
    """Context extracted from knowledge graph for LLM."""

    seed_entities: list[dict] = field(default_factory=list)
    related_entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)
    entity_mentions: dict[str, list[dict]] = field(default_factory=dict)


@dataclass
class HybridSearchResult:
    """Result from hybrid GraphRAG search."""

    success: bool
    context: GraphContext
    query_type: str = "hybrid"
    answer: str | None = None
    follow_up_suggestions: list[str] = field(default_factory=list)
    entities_found: list[dict] = field(default_factory=list)


class HybridGraphRAG:
    """
    Single unified hybrid GraphRAG approach combining:
    1. Vector similarity to find seed segments
    2. Graph neighborhood expansion
    3. Subgraph context for LLM

    Replaces dual-path approach (function-calling + GraphRAG fallback).
    """

    def __init__(
        self,
        kg_store: KnowledgeGraphStore,
        entity_extractor: QueryEntityExtractor,
        embedding_service: EmbeddingService,
        max_hops: int = 2,
        segments_per_entity: int = 5,
        vector_top_k: int = 10,
        fuzzy_threshold: int = 80,
        max_relationships: int = 20,
        max_related_entities: int = 8,
    ):
        """Initialize hybrid GraphRAG.

        Args:
            kg_store: Knowledge graph storage layer
            entity_extractor: Query entity extraction for finding seed entities
            embedding_service: Embedding service for vector similarity
            max_hops: Maximum graph hops for neighborhood expansion
            segments_per_entity: Max segments per entity to retrieve
            vector_top_k: Top-k results from vector similarity
            fuzzy_threshold: Fuzzy matching threshold for entities
        """
        self.kg_store = kg_store
        self.entity_extractor = entity_extractor
        self.embedding_service = embedding_service
        self.max_hops = max_hops
        self.segments_per_entity = segments_per_entity
        self.vector_top_k = vector_top_k
        self.fuzzy_threshold = fuzzy_threshold
        self.max_relationships = max_relationships
        self.max_related_entities = max_related_entities

    async def search(
        self,
        db: AsyncSession,
        query: str,
        max_context_segments: int = 15,
    ) -> HybridSearchResult:
        """
        Execute hybrid GraphRAG search with single unified approach.

        Flow:
        1. Extract entities from query
        2. Match entities to knowledge graph
        3. Vector search for relevant segments
        4. Expand graph neighborhood (N-hop)
        5. Build unified GraphContext
        6. Return context ready for LLM synthesis

        Args:
            db: Database session
            query: User's natural language query
            max_context_segments: Maximum segments to include in context

        Returns:
            HybridSearchResult with graph context and tool-formatted data
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Hybrid GraphRAG search: '{query}'")

        context = GraphContext()

        entities_from_query = []
        if self.entity_extractor and self._should_use_llm_entity_extraction(query):
            entities_from_query = self.entity_extractor.extract(query)
            logger.info(f"   Extracted {len(entities_from_query)} entities from query")
        else:
            logger.info("   Skipping LLM entity extraction")

        matched_entities = await self._match_entities_to_kg(db, entities_from_query)
        logger.info(f"   Matched {len(matched_entities)} entities to KG")

        if matched_entities:
            entity_ids = [m["entity_id"] for m in matched_entities]
            context.seed_entities = matched_entities

            neighborhood = await self._expand_neighborhood(db, entity_ids)
            context.related_entities = neighborhood["related_entities"]
            context.relationships = neighborhood["relationships"]

            segments_by_entity = await self._get_segments_for_entities(
                db, entity_ids, self.segments_per_entity
            )
            context.segments = segments_by_entity[:max_context_segments]

            entity_mentions = await self._get_mentions_for_entities(db, entity_ids)
            context.entity_mentions = entity_mentions

            logger.info(
                f"   Graph context: {len(context.seed_entities)} seed entities, "
                f"{len(context.related_entities)} related, {len(context.relationships)} relationships, "
                f"{len(context.segments)} segments, {len(context.entity_mentions)} mentions"
            )

        vector_results = await self.kg_store.search_semantic_with_entities(
            db, query, self.embedding_service, self.vector_top_k
        )

        if vector_results:
            vector_segments = vector_results[:5]
            logger.info(f"   Vector search: {len(vector_segments)} segments")
            context.segments.extend(vector_segments)

            if not context.seed_entities:
                derived_entities = self._extract_seed_entities_from_segments(vector_segments)
                if derived_entities:
                    context.seed_entities = derived_entities
                    entity_ids = [entity["entity_id"] for entity in derived_entities]

                    neighborhood = await self._expand_neighborhood(db, entity_ids, max_hops=1)
                    context.related_entities = neighborhood["related_entities"]
                    context.relationships = neighborhood["relationships"]

        if not context.seed_entities and not context.segments:
            logger.warning("   No results from entity matching or vector search")
            return HybridSearchResult(
                success=False,
                context=context,
                query_type="empty",
            )

        context.segments = self._dedupe_segments(context.segments)

        return HybridSearchResult(
            success=True,
            context=context,
            query_type="hybrid",
            entities_found=context.seed_entities + context.related_entities,
        )

    async def _match_entities_to_kg(
        self,
        db: AsyncSession,
        query_entities: list,
    ) -> list[dict]:
        """Match query entities to knowledge graph entities."""
        from thefuzz import fuzz

        matched = []

        for qe in query_entities:
            result = await db.execute(
                select(Entity)
                .where((Entity.name.ilike(qe.name)) | (Entity.canonical_name.ilike(qe.name)))
                .order_by(
                    Entity.importance_score.desc().nullslast(),
                    Entity.entity_confidence.desc().nullslast(),
                    Entity.updated_at.desc().nullslast(),
                    Entity.name.asc(),
                )
                .limit(1)
            )
            entity = result.scalar_one_or_none()

            if entity:
                matched.append(
                    {
                        "query_name": qe.name,
                        "entity_id": entity.entity_id,
                        "name": entity.name,
                        "canonical_name": entity.canonical_name,
                        "type": entity.entity_type,
                        "importance": entity.importance_score,
                        "confidence": entity.entity_confidence,
                    }
                )
                continue

            candidates = await self._find_candidate_entities(db, qe.name)
            if not candidates:
                continue

            best_match = None
            best_score = 0

            for entity in candidates:
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
                    {
                        "query_name": qe.name,
                        "entity_id": best_match.entity_id,
                        "name": best_match.name,
                        "canonical_name": best_match.canonical_name,
                        "type": best_match.entity_type,
                        "importance": best_match.importance_score,
                        "confidence": best_match.entity_confidence,
                        "match_type": "fuzzy",
                        "match_score": best_score,
                    }
                )

        return matched

    async def _find_candidate_entities(self, db: AsyncSession, name: str) -> list[Entity]:
        """Find a narrowed set of entity candidates for fuzzy matching."""
        if not name:
            return []

        tokens = [token for token in name.split() if len(token) > 2]
        pattern = f"%{tokens[0]}%" if tokens else f"%{name}%"

        result = await db.execute(
            select(Entity).where(
                (Entity.name.ilike(pattern)) | (Entity.canonical_name.ilike(pattern))
            )
        )

        return list(result.scalars().all())

    async def _expand_neighborhood(
        self,
        db: AsyncSession,
        entity_ids: list[str],
        max_hops: int | None = None,
    ) -> dict[str, Any]:
        """Expand N-hop neighborhood from seed entities with full relationship details."""
        if not entity_ids:
            return {"related_entities": [], "relationships": []}

        hop_limit = self.max_hops if max_hops is None else max_hops

        entity_ids_str = ", ".join(f"'{eid}'" for eid in entity_ids)

        # Bidirectional CTE that properly traverses both directions and captures relationship details
        cte_query = f"""
        WITH RECURSIVE entity_hops AS (
            -- Seed: Start from seed entities in both directions
            SELECT
                source_id as from_entity_id,
                target_id as to_entity_id,
                relation_type,
                evidence,
                confidence,
                1 as hop_count,
                CAST(source_id AS TEXT) || ' ->[' || relation_type || ']-> ' || target_id as path
            FROM relationships
            WHERE source_id IN ({entity_ids_str}) OR target_id IN ({entity_ids_str})

            UNION ALL

            -- Recursive step: Traverse in either direction
            SELECT
                CASE
                    WHEN r.source_id = eh.to_entity_id THEN r.source_id
                    ELSE r.target_id
                END as from_entity_id,
                CASE
                    WHEN r.source_id = eh.to_entity_id THEN r.target_id
                    ELSE r.source_id
                END as to_entity_id,
                r.relation_type,
                r.evidence,
                r.confidence,
                eh.hop_count + 1,
                CASE
                    WHEN r.source_id = eh.to_entity_id
                        THEN eh.path || ' ->[' || r.relation_type || ']-> ' || r.target_id
                    ELSE eh.path || ' <-[' || r.relation_type || ']- ' || r.source_id
                END as path
            FROM relationships r
            JOIN entity_hops eh ON (
                (r.source_id = eh.to_entity_id AND r.target_id != eh.from_entity_id)
                OR (r.target_id = eh.to_entity_id AND r.source_id != eh.from_entity_id)
            )
            WHERE eh.hop_count < {hop_limit}
        )
        SELECT DISTINCT
            from_entity_id,
            to_entity_id,
            relation_type,
            evidence,
            confidence,
            hop_count,
            path
        FROM entity_hops
        ORDER BY hop_count, from_entity_id, to_entity_id
        """

        result = await db.execute(text(cte_query))
        rows = result.fetchall()

        related_entities = set(entity_ids)  # Start with seed entities
        relationships = []

        for row in rows:
            # Add both ends of relationship to related entities
            related_entities.add(row.from_entity_id)
            related_entities.add(row.to_entity_id)

            relationships.append(
                {
                    "source_id": row.from_entity_id,
                    "target_id": row.to_entity_id,
                    "relation_type": row.relation_type,
                    "evidence": row.evidence,
                    "confidence": row.confidence,
                    "hop_count": row.hop_count,
                    "path": row.path,
                }
            )

        entity_details = await self._get_entity_details(db, list(related_entities))

        name_map = {
            entity_id: details.get("name", entity_id)
            for entity_id, details in entity_details.items()
        }

        related_entities_list = [
            {
                "entity_id": entity_id,
                "name": details.get("name", ""),
                "type": details.get("entity_type", ""),
                "importance": details.get("importance_score", 0.0),
                "is_seed": entity_id in entity_ids,
            }
            for entity_id, details in entity_details.items()
        ][: self.max_related_entities]

        relationships_sample = []
        for rel in relationships[: self.max_relationships]:
            path_ids = [seg.strip() for seg in rel.get("path", "").split("->") if seg.strip()]
            path_names = " -> ".join(name_map.get(pid, pid) for pid in path_ids)
            rel["path_names"] = path_names
            relationships_sample.append(rel)

        return {
            "related_entities": related_entities_list,
            "relationships": relationships_sample,
        }

    async def _get_entity_details(
        self,
        db: AsyncSession,
        entity_ids: list[str],
    ) -> dict[str, dict]:
        """Get details for multiple entities."""
        if not entity_ids:
            return {}

        result = await db.execute(select(Entity).where(Entity.entity_id.in_(entity_ids)))
        entities = result.scalars().all()

        return {
            entity.entity_id: {
                "name": entity.name,
                "type": entity.entity_type,
                "importance_score": entity.importance_score,
            }
            for entity in entities
        }

    async def _get_segments_for_entities(
        self,
        db: AsyncSession,
        entity_ids: list[str],
        limit_per_entity: int,
    ) -> list[dict]:
        """Get transcript segments mentioning given entities."""
        if not entity_ids:
            return []

        entity_ids_list = list(entity_ids)

        from models.mention import Mention

        result = await db.execute(
            select(
                TranscriptSegment,
                Entity,
                Mention,
                Video,
            )
            .join(Mention, TranscriptSegment.segment_id == Mention.segment_id)
            .join(Entity, Mention.entity_id == Entity.entity_id)
            .join(Video, TranscriptSegment.video_id == Video.id)
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
                    "video": row.Video,
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
        entity_segment_counts = dict.fromkeys(entity_ids_list, 0)

        for seg_id, data in segment_map.items():
            has_new_entity = False
            for entity in data["entities"]:
                eid = entity["entity_id"]
                if entity_segment_counts[eid] < limit_per_entity:
                    entity_segment_counts[eid] += 1
                    has_new_entity = True

            if has_new_entity:
                video = data.get("video")
                segments.append(
                    {
                        "segment_id": seg_id,
                        "text": data["segment"].text,
                        "video_id": str(data["segment"].video_id),
                        "video_title": video.title if video else "Unknown",
                        "youtube_id": video.youtube_id if video else None,
                        "youtube_url": video.youtube_url if video else None,
                        "session_date": (
                            video.session_date.isoformat() if video and video.session_date else None
                        ),
                        "speaker_id": data["segment"].speaker_id,
                        "timestamp_seconds": data["segment"].start_time_seconds,
                        "entities": data["entities"],
                    }
                )

        return segments

    def _extract_seed_entities_from_segments(self, segments: list[dict]) -> list[dict]:
        """Derive seed entities from semantic segments."""
        counts: dict[str, dict] = {}

        for seg in segments:
            for entity in seg.get("entities", []):
                entity_id = entity.get("entity_id")
                if not entity_id:
                    continue

                if entity_id not in counts:
                    counts[entity_id] = {
                        "entity_id": entity_id,
                        "name": entity.get("name", ""),
                        "type": entity.get("entity_type", ""),
                        "importance": entity.get("importance_score", 0.0),
                        "match_type": "segment",
                        "count": 0,
                    }

                counts[entity_id]["count"] += 1

        ranked = sorted(
            counts.values(),
            key=lambda item: (item["count"], item.get("importance", 0.0)),
            reverse=True,
        )

        return [
            {
                "entity_id": item["entity_id"],
                "name": item["name"],
                "type": item["type"],
                "importance": item.get("importance", 0.0),
                "match_type": item.get("match_type"),
            }
            for item in ranked[:3]
        ]

    def _should_use_llm_entity_extraction(self, query: str) -> bool:
        """Heuristic for when to call LLM entity extraction."""
        if not query:
            return False

        tokens = [token for token in query.split() if token.strip()]
        if len(tokens) <= 3 and query.islower():
            return False

        letters = [char for char in query if char.isalpha()]
        upper_count = sum(1 for char in letters if char.isupper())
        if upper_count <= 1 and query[:1].isupper():
            return False
        if upper_count > 1:
            return True

        if any(char.isdigit() for char in query):
            return True

        if '"' in query or "'" in query:
            return True

        return len(tokens) > 6

    def _dedupe_segments(self, segments: list[dict]) -> list[dict]:
        """Deduplicate segments by segment_id."""
        seen = set()
        deduped = []
        for seg in segments:
            seg_id = seg.get("segment_id")
            if not seg_id or seg_id in seen:
                continue
            seen.add(seg_id)
            deduped.append(seg)
        return deduped

    async def _get_mentions_for_entities(
        self,
        db: AsyncSession,
        entity_ids: list[str],
    ) -> dict[str, list[dict]]:
        """Get all mentions for given entities."""
        if not entity_ids:
            return {}

        from models.mention import Mention

        result = await db.execute(select(Mention).where(Mention.entity_id.in_(entity_ids)))
        mentions = result.scalars().all()

        mentions_map: dict[str, list[dict]] = {}
        for mention in mentions:
            eid = mention.entity_id
            if eid not in mentions_map:
                mentions_map[eid] = []

            mentions_map[eid].append(
                {
                    "text": mention.context,
                    "timestamp": mention.timestamp_seconds,
                    "video_id": mention.video_id,
                    "speaker": mention.speaker_id,
                    "segment_id": mention.segment_id,
                    "speaker_canonical_id": mention.speaker_canonical_id,
                }
            )

        return mentions_map

    async def _get_video_for_segment(
        self,
        db: AsyncSession,
        video_id: str | None,
    ) -> Video | None:
        """Get video metadata for a segment."""
        if not video_id:
            return None
        try:
            from models.video import Video

            result = await db.execute(select(Video).where(Video.id == video_id))
            return result.scalar_one_or_none()
        except Exception:
            return None
