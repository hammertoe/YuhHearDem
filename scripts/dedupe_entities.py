#!/usr/bin/env python3
"""Post-ingest deduplication for knowledge graph entities."""

import sys
from pathlib import Path

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from core.database import get_db
from models.community import EntityCommunity
from models.entity import Entity
from models.mention import Mention
from models.relationship import Relationship
from services.gemini import GeminiClient

logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_FUZZY_THRESHOLD = 92
EXCLUDED_ENTITY_TYPES = {"agenda_item"}


@dataclass
class MergeAction:
    """Represents a single merge decision from the LLM."""

    survivor_id: str
    merge_ids: list[str]
    confidence: float
    reason: str | None = None


@dataclass
class MergePlan:
    """Collection of merge actions to apply."""

    actions: list[MergeAction] = field(default_factory=list)


def _create_placeholder_video_id() -> UUID:
    return uuid4()


def _normalize_name(value: str) -> str:
    return " ".join("".join(ch for ch in value.lower() if ch.isalnum() or ch.isspace()).split())


def can_merge_entities(entity_a: Entity, entity_b: Entity) -> bool:
    if entity_a.entity_type != entity_b.entity_type:
        return False
    if (
        entity_a.speaker_canonical_id
        and entity_b.speaker_canonical_id
        and entity_a.speaker_canonical_id != entity_b.speaker_canonical_id
    ):
        return False
    return True


def _build_llm_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "merges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "survivor_id": {"type": "string"},
                        "merge_ids": {"type": "array", "items": {"type": "string"}},
                        "confidence": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["survivor_id", "merge_ids", "confidence"],
                },
            }
        },
        "required": ["merges"],
    }


async def _fetch_entity_stats(db: AsyncSession, entity_ids: list[str]) -> dict[str, dict]:
    if not entity_ids:
        return {}

    stats: dict[str, dict[str, Any]] = {
        eid: {"mentions": 0, "relationships": 0} for eid in entity_ids
    }

    mention_counts = await db.execute(
        select(Mention.entity_id, func.count(Mention.id))
        .where(Mention.entity_id.in_(entity_ids))
        .group_by(Mention.entity_id)
    )
    for entity_id, count in mention_counts:
        stats[entity_id]["mentions"] = int(count)

    rel_source_counts = await db.execute(
        select(Relationship.source_id, func.count(Relationship.id))
        .where(Relationship.source_id.in_(entity_ids))
        .group_by(Relationship.source_id)
    )
    for entity_id, count in rel_source_counts:
        stats[entity_id]["relationships"] += int(count)

    rel_target_counts = await db.execute(
        select(Relationship.target_id, func.count(Relationship.id))
        .where(Relationship.target_id.in_(entity_ids))
        .group_by(Relationship.target_id)
    )
    for entity_id, count in rel_target_counts:
        stats[entity_id]["relationships"] += int(count)

    return stats


def _build_entity_context(entity: Entity, stats: dict[str, Any]) -> dict[str, Any]:
    meta_data = entity.meta_data or {}
    evidence = meta_data.get("evidence")
    attributes = meta_data.get("attributes")

    return {
        "entity_id": entity.entity_id,
        "name": entity.name,
        "canonical_name": entity.canonical_name,
        "aliases": entity.aliases or [],
        "entity_type": entity.entity_type,
        "entity_subtype": entity.entity_subtype,
        "description": entity.description,
        "speaker_canonical_id": entity.speaker_canonical_id,
        "source": entity.source,
        "source_ref": entity.source_ref,
        "first_seen_date": entity.first_seen_date.isoformat() if entity.first_seen_date else None,
        "mentions": stats.get("mentions", 0),
        "relationships": stats.get("relationships", 0),
        "evidence": evidence,
        "attributes": attributes,
    }


def _build_prompt(cluster_context: list[dict[str, Any]]) -> str:
    return (
        "You are deduplicating knowledge graph entities. "
        "Given the list of entity records, decide which represent the same real-world entity. "
        "Only merge entities that clearly refer to the same thing. "
        "Return merges with a single survivor_id and list of merge_ids. "
        "Do not merge if unsure.\n\n"
        f"Entities:\n{cluster_context}"
    )


def _select_survivor(entities: list[Entity], stats: dict[str, dict[str, Any]]) -> Entity:
    def score(entity: Entity) -> tuple[int, int, datetime]:
        stat = stats.get(entity.entity_id, {})
        rel_count = int(stat.get("relationships", 0))
        mention_count = int(stat.get("mentions", 0))
        created_at = entity.created_at or datetime.min
        return (rel_count, mention_count, created_at)

    return sorted(entities, key=score, reverse=True)[0]


def _merge_entity_attributes(survivor: Entity, duplicates: list[Entity]) -> None:
    aliases = set(survivor.aliases or [])
    if survivor.name:
        aliases.add(survivor.name)
    if survivor.canonical_name:
        aliases.add(survivor.canonical_name)

    merged_ids = set()
    merged_meta = dict(survivor.meta_data or {})
    for duplicate in duplicates:
        if duplicate.name:
            aliases.add(duplicate.name)
        if duplicate.canonical_name:
            aliases.add(duplicate.canonical_name)
        aliases.update(duplicate.aliases or [])
        merged_ids.add(duplicate.entity_id)

        if not survivor.description and duplicate.description:
            survivor.description = duplicate.description
        if not survivor.speaker_canonical_id and duplicate.speaker_canonical_id:
            survivor.speaker_canonical_id = duplicate.speaker_canonical_id

        duplicate_meta = duplicate.meta_data or {}
        for key, value in duplicate_meta.items():
            if key not in merged_meta:
                merged_meta[key] = value

    merged_meta_ids = set(merged_meta.get("merged_entity_ids", []))
    merged_meta_ids.update(merged_ids)
    merged_meta["merged_entity_ids"] = sorted(merged_meta_ids)
    survivor.meta_data = merged_meta
    survivor.aliases = sorted(aliases)


async def apply_merge_plan(db: AsyncSession, plan: MergePlan) -> None:
    if not plan.actions:
        return

    for action in plan.actions:
        if not action.merge_ids:
            continue

        merge_ids = list(dict.fromkeys(action.merge_ids))
        survivor_id = action.survivor_id

        entities = await db.execute(
            select(Entity).where(Entity.entity_id.in_([survivor_id, *merge_ids]))
        )
        entity_map = {entity.entity_id: entity for entity in entities.scalars().all()}
        survivor = entity_map.get(survivor_id)
        if not survivor:
            continue

        duplicates = [entity_map[eid] for eid in merge_ids if eid in entity_map]
        if not duplicates:
            continue

        await db.execute(
            update(Mention).where(Mention.entity_id.in_(merge_ids)).values(entity_id=survivor_id)
        )

        await db.execute(
            update(Relationship)
            .where(Relationship.source_id.in_(merge_ids))
            .values(source_id=survivor_id)
        )
        await db.execute(
            update(Relationship)
            .where(Relationship.target_id.in_(merge_ids))
            .values(target_id=survivor_id)
        )

        await db.execute(
            update(EntityCommunity)
            .where(EntityCommunity.entity_id.in_(merge_ids))
            .values(entity_id=survivor_id)
        )

        _merge_entity_attributes(survivor, duplicates)

        for duplicate in duplicates:
            await db.delete(duplicate)

    await db.flush()


async def _load_entities(
    db: AsyncSession,
    include_types: set[str] | None,
    exclude_types: set[str],
    limit: int | None,
) -> list[Entity]:
    query = select(Entity)
    if include_types:
        query = query.where(Entity.entity_type.in_(include_types))
    if exclude_types:
        query = query.where(~Entity.entity_type.in_(exclude_types))
    if limit:
        query = query.limit(limit)
    result = await db.execute(query)
    return [entity for entity in result.scalars().all()]


def _build_clusters(entities: list[Entity], threshold: int) -> list[list[Entity]]:
    from thefuzz import fuzz

    clusters: list[list[Entity]] = []
    used: set[str] = set()

    for entity in entities:
        if entity.entity_id in used:
            continue
        cluster = [entity]
        used.add(entity.entity_id)

        for candidate in entities:
            if candidate.entity_id in used:
                continue
            if not can_merge_entities(entity, candidate):
                continue

            name_a = _normalize_name(entity.canonical_name or entity.name or "")
            name_b = _normalize_name(candidate.canonical_name or candidate.name or "")
            if not name_a or not name_b:
                continue
            if fuzz.ratio(name_a, name_b) >= threshold:
                cluster.append(candidate)
                used.add(candidate.entity_id)

        if len(cluster) > 1:
            clusters.append(cluster)

    return clusters


async def _llm_merge_plan(
    db: AsyncSession,
    client: GeminiClient,
    cluster: list[Entity],
    confidence_threshold: float,
) -> MergePlan:
    entity_ids = [entity.entity_id for entity in cluster]
    stats = await _fetch_entity_stats(db, entity_ids)
    context = [_build_entity_context(entity, stats.get(entity.entity_id, {})) for entity in cluster]
    prompt = _build_prompt(context)
    response = client.generate_structured(prompt, _build_llm_schema(), stage="entity_dedupe")

    actions: list[MergeAction] = []
    for item in response.get("merges", []):
        try:
            action = MergeAction(
                survivor_id=item["survivor_id"],
                merge_ids=list(item.get("merge_ids", [])),
                confidence=float(item.get("confidence", 0.0)),
                reason=item.get("reason"),
            )
        except (KeyError, ValueError, TypeError):
            continue

        if action.confidence < confidence_threshold:
            continue

        if action.survivor_id not in entity_ids:
            continue
        action.merge_ids = [eid for eid in action.merge_ids if eid in entity_ids]
        if not action.merge_ids:
            continue

        survivor = next(
            (entity for entity in cluster if entity.entity_id == action.survivor_id), None
        )
        if not survivor:
            continue

        duplicates = [entity for entity in cluster if entity.entity_id in action.merge_ids]
        if any(not can_merge_entities(survivor, duplicate) for duplicate in duplicates):
            continue

        actions.append(action)

    return MergePlan(actions=actions)


async def run_dedupe(
    confidence: float,
    fuzzy_threshold: int,
    include_types: set[str] | None,
    exclude_types: set[str],
    limit: int | None,
    dry_run: bool,
    model: str | None,
    temperature: float | None,
) -> int:
    settings = get_settings()
    client = GeminiClient(
        api_key=settings.google_api_key,
        model=model or settings.gemini_model,
        temperature=temperature if temperature is not None else settings.gemini_temperature,
    )

    total_merges = 0
    async for db in get_db():
        entities = await _load_entities(db, include_types, exclude_types, limit)
        clusters = _build_clusters(entities, threshold=fuzzy_threshold)
        logger.info("Found %s candidate clusters", len(clusters))

        for cluster in clusters:
            plan = await _llm_merge_plan(db, client, cluster, confidence)
            total_merges += sum(len(action.merge_ids) for action in plan.actions)

            if dry_run:
                logger.info("Dry run merge plan: %s", plan)
                continue

            await apply_merge_plan(db, plan)

    return total_merges


def _parse_type_list(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate knowledge graph entities")
    parser.add_argument(
        "--confidence",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="Minimum LLM confidence required to merge (default: 0.85)",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=DEFAULT_FUZZY_THRESHOLD,
        help="Fuzzy matching threshold for candidate clusters (default: 92)",
    )
    parser.add_argument(
        "--types",
        help="Comma-separated entity types to include",
    )
    parser.add_argument(
        "--exclude-types",
        help="Comma-separated entity types to exclude",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of entities scanned",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show merge plan without writing changes",
    )
    parser.add_argument(
        "--model",
        help="Gemini model override",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="Gemini temperature override",
    )

    args = parser.parse_args()

    exclude_types = set(EXCLUDED_ENTITY_TYPES)
    exclude_override = _parse_type_list(args.exclude_types)
    if exclude_override is not None:
        exclude_types = exclude_override

    include_types = _parse_type_list(args.types)

    total_merges = await run_dedupe(
        confidence=args.confidence,
        fuzzy_threshold=args.fuzzy_threshold,
        include_types=include_types,
        exclude_types=exclude_types,
        limit=args.limit,
        dry_run=args.dry_run,
        model=args.model,
        temperature=args.temperature,
    )

    logger.info("Merged %s entities", total_merges)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(main())
