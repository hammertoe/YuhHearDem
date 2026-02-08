"""Batch entity deduplication script.

This script runs periodically (not on-the-fly) to:
1. Find similar entities using hybrid matching (fuzzy + vector)
2. Use LLM to resolve ambiguous cases
3. Merge duplicate entities
4. Update relationship references

Usage:
    python scripts/run_deduplication.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    GOOGLE_API_KEY: Gemini API key
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_session_maker
from models.entity import Entity
from models.relationship import Relationship
from services.entity_deduplication import EntityDeduplicationService
from services.gemini import GeminiClient

settings = get_settings()


async def remap_relationships(
    session: AsyncSession,
    id_mapping: dict[str, str],
) -> int:
    """
    Remap relationship references after entity merging.

    Args:
        session: Database session
        id_mapping: Mapping of old entity IDs to new canonical IDs

    Returns:
        Number of relationships updated
    """
    updated_count = 0

    # Get all relationships that need remapping
    result = await session.execute(select(Relationship))
    relationships = result.scalars().all()

    for relationship in relationships:
        original_source = relationship.source_entity_id
        original_target = relationship.target_entity_id

        # Remap source if needed
        new_source = id_mapping.get(original_source, original_source)
        if new_source != original_source:
            relationship.source_entity_id = new_source
            updated_count += 1

        # Remap target if needed
        new_target = id_mapping.get(original_target, original_target)
        if new_target != original_target:
            relationship.target_entity_id = new_target
            updated_count += 1

    return updated_count


async def run_deduplication() -> None:
    """Run the deduplication process."""
    session_maker = get_session_maker()

    async with session_maker() as session:
        print("Initializing deduplication service...")

        # Initialize Gemini client
        gemini_client = GeminiClient(
            api_key=settings.google_api_key,
            model="gemini-3-flash-preview",
            temperature=0.0,
        )

        # Initialize deduplication service
        dedup_service = EntityDeduplicationService(
            session=session,
            gemini_client=gemini_client,
            fuzzy_threshold=0.85,
            vector_threshold=0.85,
            hybrid_threshold=0.80,
            batch_size=50,
        )

        print("Starting entity deduplication...")
        print(f"Fuzzy threshold: {dedup_service.fuzzy_threshold}")
        print(f"Vector threshold: {dedup_service.vector_threshold}")
        print(f"Hybrid threshold: {dedup_service.hybrid_threshold}")
        print()

        try:
            # Run deduplication
            stats = await dedup_service.run_deduplication()

            print("\nDeduplication Results:")
            print(f"  Entities processed: {stats['entities_processed']}")
            print(f"  Pairs checked: {stats['pairs_checked']}")
            print(f"  Matches found: {stats['matches_found']}")
            print(f"  Entities merged: {stats['merged']}")
            print(f"  Kept separate: {stats['kept_separate']}")

            if stats["errors"]:
                print(f"\nErrors encountered:")
                for error in stats["errors"]:
                    print(f"  - {error}")

            # Get ID mapping for relationship remapping
            print("\nRemapping relationships...")
            id_mapping = await dedup_service.get_entity_id_mapping()

            if id_mapping:
                updated = await remap_relationships(session, id_mapping)
                print(f"  Updated {updated} relationship references")

            # Commit all changes
            await session.commit()
            print("\nDeduplication complete!")

        except Exception as e:
            await session.rollback()
            print(f"\nError during deduplication: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(run_deduplication())
