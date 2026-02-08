"""Global entity deduplication service using batch processing."""

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from core.config import get_settings
from models.entity import Entity
from services.embeddings import EmbeddingService
from services.gemini import GeminiClient
from services.schemas import DEDUPLICATION_SCHEMA

settings = get_settings()


@dataclass
class EntityMatch:
    """Potential entity match for deduplication."""

    entity1: Entity
    entity2: Entity
    fuzzy_score: float
    vector_score: float
    hybrid_score: float


class EntityDeduplicationService:
    """
    Batch-based global entity deduplication service.

    This service runs periodically (not on-the-fly) to:
    1. Find similar entities using hybrid matching (fuzzy + vector)
    2. Use LLM to resolve ambiguous cases
    3. Merge duplicate entities
    4. Remap relationship references
    """

    def __init__(
        self,
        session: AsyncSession,
        gemini_client: GeminiClient,
        fuzzy_threshold: float = 0.85,
        vector_threshold: float = 0.85,
        hybrid_threshold: float = 0.80,
        batch_size: int = 100,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """
        Initialize deduplication service.

        Args:
            session: Database session
            gemini_client: Gemini client for ambiguity resolution
            fuzzy_threshold: Minimum fuzzy match score (0-1)
            vector_threshold: Minimum vector similarity (0-1)
            hybrid_threshold: Minimum hybrid score (0-1)
            batch_size: Number of entities to process per batch
            embedding_service: Embedding service (if None, creates one)
        """
        self.session = session
        self.gemini_client = gemini_client
        self.fuzzy_threshold = fuzzy_threshold
        self.vector_threshold = vector_threshold
        self.hybrid_threshold = hybrid_threshold
        self.batch_size = batch_size
        self.embedding_service = embedding_service or EmbeddingService()

    async def run_deduplication(self) -> dict[str, Any]:
        """
        Run full deduplication process on all entities.

        Returns:
            Statistics about the deduplication process
        """
        stats = {
            "entities_processed": 0,
            "pairs_checked": 0,
            "matches_found": 0,
            "merged": 0,
            "kept_separate": 0,
            "errors": [],
        }

        try:
            # Get all entities ordered by creation date (oldest first)
            result = await self.session.execute(select(Entity).order_by(Entity.created_at))
            all_entities = list(result.scalars().all())

            if len(all_entities) < 2:
                return stats

            # Ensure all entities have embeddings
            await self._ensure_embeddings(all_entities)

            # Find candidate pairs using hybrid matching
            candidate_pairs = await self._find_candidate_pairs(all_entities)
            stats["pairs_checked"] = len(candidate_pairs)

            # Process candidate pairs in batches
            for i in range(0, len(candidate_pairs), self.batch_size):
                batch = candidate_pairs[i : i + self.batch_size]

                for match in batch:
                    stats["entities_processed"] += 1

                    # Resolve ambiguous matches with LLM
                    decision = await self._resolve_match(match)

                    if decision["decision"] == "merge":
                        await self._merge_entities(
                            match.entity1,
                            match.entity2,
                            decision,
                        )
                        stats["merged"] += 1
                    else:
                        stats["kept_separate"] += 1

                    stats["matches_found"] += 1

            await self.session.commit()

        except Exception as e:
            stats["errors"].append(str(e))
            await self.session.rollback()
            raise

        return stats

    async def _ensure_embeddings(self, entities: list[Entity]) -> None:
        """Ensure all entities have embeddings computed."""
        entities_needing_embeddings = [e for e in entities if e.embedding is None]

        if not entities_needing_embeddings:
            return

        # Compute embeddings in batches
        batch_size = 32
        for i in range(0, len(entities_needing_embeddings), batch_size):
            batch = entities_needing_embeddings[i : i + batch_size]

            # Create texts for embedding
            texts = []
            for entity in batch:
                text = f"{entity.canonical_name} - {entity.description or ''}"
                texts.append(text)

            # Compute embeddings using EmbeddingService
            embeddings = self.embedding_service.generate_embeddings(texts)

            # Assign embeddings
            for entity, embedding in zip(batch, embeddings):
                entity.embedding = embedding

        await self.session.flush()

    async def _find_candidate_pairs(self, entities: list[Entity]) -> list[EntityMatch]:
        """
        Find candidate entity pairs for deduplication.

        Uses hybrid scoring: 30% fuzzy + 70% vector similarity
        """
        candidate_pairs = []

        # Compare each entity with entities created after it
        # (to avoid duplicate comparisons and maintain ordering)
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1 :]:
                # Only compare entities of the same type
                if entity1.entity_type != entity2.entity_type:
                    continue

                # Calculate fuzzy score
                fuzzy_score = self._calculate_fuzzy_score(entity1, entity2)

                # Calculate vector score if both have embeddings
                vector_score = 0.0
                if entity1.embedding and entity2.embedding:
                    vector_score = self._calculate_vector_similarity(
                        entity1.embedding, entity2.embedding
                    )

                # Calculate hybrid score
                hybrid_score = (0.3 * fuzzy_score) + (0.7 * vector_score)

                # Check if this pair meets thresholds
                if (
                    fuzzy_score >= self.fuzzy_threshold
                    or vector_score >= self.vector_threshold
                    or hybrid_score >= self.hybrid_threshold
                ):
                    match = EntityMatch(
                        entity1=entity1,
                        entity2=entity2,
                        fuzzy_score=fuzzy_score,
                        vector_score=vector_score,
                        hybrid_score=hybrid_score,
                    )
                    candidate_pairs.append(match)

        # Sort by hybrid score (highest first)
        candidate_pairs.sort(key=lambda m: m.hybrid_score, reverse=True)

        return candidate_pairs

    def _calculate_fuzzy_score(self, entity1: Entity, entity2: Entity) -> float:
        """Calculate fuzzy matching score between two entities."""
        # Check canonical names
        names_to_check1 = [entity1.canonical_name, entity1.name] + entity1.aliases
        names_to_check2 = [entity2.canonical_name, entity2.name] + entity2.aliases

        best_score = 0.0
        for name1 in names_to_check1:
            for name2 in names_to_check2:
                score = fuzz.ratio(name1.lower(), name2.lower()) / 100.0
                best_score = max(best_score, score)

        return best_score

    def _calculate_vector_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def _resolve_match(self, match: EntityMatch) -> dict[str, Any]:
        """
        Use LLM to resolve ambiguous entity matches.

        Returns:
            Decision dict with 'decision', 'reasoning', and optional merge fields
        """
        prompt = self._build_deduplication_prompt(match)

        result = self.gemini_client.generate_structured(
            prompt=prompt,
            response_schema=DEDUPLICATION_SCHEMA,
            stage="entity_deduplication",
        )

        return result

    def _build_deduplication_prompt(self, match: EntityMatch) -> str:
        """Build prompt for LLM deduplication decision."""
        entity1 = match.entity1
        entity2 = match.entity2

        prompt = f"""Determine if these two entities should be merged or kept separate.

## Entity 1
- ID: {entity1.entity_id}
- Name: {entity1.name}
- Canonical Name: {entity1.canonical_name}
- Type: {entity1.entity_type}
- Description: {entity1.description or "N/A"}
- Aliases: {", ".join(entity1.aliases) or "None"}

## Entity 2
- ID: {entity2.entity_id}
- Name: {entity2.name}
- Canonical Name: {entity2.canonical_name}
- Type: {entity2.entity_type}
- Description: {entity2.description or "N/A"}
- Aliases: {", ".join(entity2.aliases) or "None"}

## Similarity Scores
- Fuzzy Score: {match.fuzzy_score:.2f}
- Vector Score: {match.vector_score:.2f}
- Hybrid Score: {match.hybrid_score:.2f}

## Decision Rules
Merge if:
- They clearly refer to the same person, organization, law, or concept
- One is an abbreviated/shortened form of the other
- They are different names for the same thing (e.g., "CARICOM" and "Caribbean Community")

Keep Separate if:
- They could be different entities (e.g., two different people with similar names)
- One is a subset/part of the other (e.g., a committee vs the full organization)
- They are related but distinct concepts

Make your decision and explain your reasoning.
"""

        return prompt

    async def _merge_entities(
        self,
        keep_entity: Entity,
        merge_entity: Entity,
        decision: dict[str, Any],
    ) -> None:
        """
        Merge two entities, keeping the older one as canonical.

        Args:
            keep_entity: The entity to keep (older one)
            merge_entity: The entity to merge into keep_entity
            decision: LLM decision with merge details
        """
        # Use merged name from decision or keep the better one
        merged_name = decision.get("merged_name", keep_entity.canonical_name)
        if merged_name != keep_entity.canonical_name:
            # Add old name as alias
            if keep_entity.canonical_name not in keep_entity.aliases:
                keep_entity.aliases.append(keep_entity.canonical_name)
            keep_entity.canonical_name = merged_name

        # Merge aliases
        merged_aliases = decision.get("merged_aliases", [])
        if not merged_aliases:
            # Combine aliases from both
            merged_aliases = list(set(keep_entity.aliases + merge_entity.aliases))
        keep_entity.aliases = merged_aliases

        # Keep the better description
        if merge_entity.description and (
            not keep_entity.description
            or len(merge_entity.description) > len(keep_entity.description)
        ):
            keep_entity.description = merge_entity.description

        # Use maximum confidence
        if merge_entity.confidence:
            keep_entity.confidence = max(
                keep_entity.confidence or 0,
                merge_entity.confidence,
            )

        # Use maximum importance
        keep_entity.importance_score = max(
            keep_entity.importance_score,
            merge_entity.importance_score,
        )

        # Merge metadata
        if merge_entity.meta_data:
            if keep_entity.meta_data is None:
                keep_entity.meta_data = {}
            keep_entity.meta_data.update(merge_entity.meta_data)

        # Store ID mapping for relationship remapping
        if keep_entity.meta_data is None:
            keep_entity.meta_data = {}

        merged_ids = keep_entity.meta_data.get("merged_entity_ids", [])
        merged_ids.append(merge_entity.entity_id)
        keep_entity.meta_data["merged_entity_ids"] = merged_ids

        # Mark merge_entity as merged
        if merge_entity.meta_data is None:
            merge_entity.meta_data = {}
        merge_entity.meta_data["merged_into"] = keep_entity.entity_id
        merge_entity.meta_data["merged_at"] = func.now()

        # We don't delete, just mark as merged - relationships will be remapped separately

    async def get_entity_id_mapping(self) -> dict[str, str]:
        """
        Get mapping of merged entity IDs to their canonical IDs.

        Returns:
            Dict mapping old entity IDs to new canonical IDs
        """
        result = await self.session.execute(select(Entity).where(Entity.meta_data.isnot(None)))
        entities = result.scalars().all()

        id_mapping = {}
        for entity in entities:
            if entity.meta_data and "merged_into" in entity.meta_data:
                id_mapping[entity.entity_id] = entity.meta_data["merged_into"]

        return id_mapping
