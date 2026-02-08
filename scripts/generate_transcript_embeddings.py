"""Generate embeddings for transcript sentences in batches.

This script:
1. Fetches transcript sentences with NULL embeddings
2. Generates vector embeddings using local sentence-transformers model
3. Generates full-text search vectors
4. Updates database with both

Usage:
    python scripts/generate_transcript_embeddings.py [--limit N] [--batch-size N]

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import to_tsvector

from core.database import get_session_maker
from models.transcript_sentence import TranscriptSentence
from services.embeddings import EmbeddingService


async def generate_embeddings_for_sentence(
    session: AsyncSession,
    sentence: TranscriptSentence,
    embedding: list[float],
    search_vector: str,
) -> None:
    """
    Update a single transcript sentence with embeddings.

    Args:
        session: Database session
        sentence: TranscriptSentence model instance
        embedding: Vector embedding (768 dims)
        search_vector: Full-text search vector
    """
    await session.execute(
        update(TranscriptSentence)
        .where(TranscriptSentence.sentence_id == sentence.sentence_id)
        .values(
            embedding=embedding,
            search_vector=search_vector,
        )
    )


async def process_batch(
    session: AsyncSession,
    sentences: list[TranscriptSentence],
    embedding_service: EmbeddingService,
) -> tuple[int, int]:
    """
    Process a batch of transcript sentences.

    Args:
        session: Database session
        sentences: List of transcript sentences
        embedding_service: Embedding service

    Returns:
        Tuple of (processed_count, error_count)
    """
    processed = 0
    errors = 0

    try:
        # Generate text embeddings (for semantic search)
        texts = [s.full_text for s in sentences]
        embeddings = embedding_service.generate_batch(
            texts=texts,
            batch_size=len(texts),
        )

        # Generate full-text search vectors (for keyword search)
        search_vectors = [to_tsvector("english", s.full_text) for s in sentences]

        # Update all sentences in batch
        for sentence, embedding, search_vector in zip(sentences, embeddings, search_vectors):
            await generate_embeddings_for_sentence(
                session=session,
                sentence=sentence,
                embedding=embedding,
                search_vector=search_vector,
            )
            processed += 1

        await session.commit()

    except Exception as e:
        print(f"Error processing batch: {e}", file=sys.stderr)
        await session.rollback()
        errors = len(sentences)

    return processed, errors


async def generate_transcript_embeddings(
    limit: int | None = None,
    batch_size: int = 100,
) -> dict:
    """
    Generate embeddings for all transcript sentences with NULL embeddings.

    Args:
        limit: Maximum number of sentences to process (for testing)
        batch_size: Number of sentences to process per batch

    Returns:
        Dictionary with statistics
    """
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Fetch sentences without embeddings
        query = select(TranscriptSentence).where(TranscriptSentence.embedding.is_(None))

        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        sentences_to_process = list(result.scalars().all())

        total_sentences = len(sentences_to_process)

        if total_sentences == 0:
            print("No transcript sentences found without embeddings.")
            return {
                "total": 0,
                "processed": 0,
                "errors": 0,
                "batches": 0,
            }

        print(f"Found {total_sentences} transcript sentences without embeddings")
        print(f"Batch size: {batch_size}")
        print()

        # Use local sentence-transformers model (no API calls needed)
        print("Using local sentence-transformers model (all-mpnet-base-v2)...")
        embedding_service = EmbeddingService()

        # Process in batches
        processed_total = 0
        errors_total = 0
        batch_count = 0

        for i in range(0, total_sentences, batch_size):
            batch = sentences_to_process[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_sentences + batch_size - 1) // batch_size

            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} sentences)...")

            processed, errors = await process_batch(
                session=session,
                sentences=batch,
                embedding_service=embedding_service,
            )

            processed_total += processed
            errors_total += errors
            batch_count += 1

            # Progress
            progress = ((i + batch_size) / total_sentences) * 100
            progress = min(progress, 100)
            print(f"  Processed: {processed}  Errors: {errors}  Progress: {progress:.1f}%")
            print()

        # Final statistics
        print("=" * 60)
        print("Embedding Generation Complete!")
        print("=" * 60)
        print(f"Total sentences: {total_sentences}")
        print(f"Processed: {processed_total}")
        print(f"Errors: {errors_total}")
        print(f"Batch count: {batch_count}")
        print(f"Success rate: {(processed_total / total_sentences * 100):.1f}%")

        # Check remaining
        remaining_query = select(func.count(TranscriptSentence.sentence_id)).where(
            TranscriptSentence.embedding.is_(None)
        )
        remaining_result = await session.execute(remaining_query)
        remaining = remaining_result.scalar()

        if remaining > 0:
            print()
            print(f"Remaining sentences without embeddings: {remaining}")
            print("Run script again to process remaining batches.")

        print()

        return {
            "total": total_sentences,
            "processed": processed_total,
            "errors": errors_total,
            "batches": batch_count,
            "remaining": remaining,
        }


async def generate_only_fulltext_vectors(limit: int | None = None, batch_size: int = 100) -> dict:
    """
    Generate only full-text search vectors (much faster, no API calls).

    Useful when you only need keyword search, not semantic search.

    Args:
        limit: Maximum number of sentences to process
        batch_size: Number of sentences to process per batch

    Returns:
        Dictionary with statistics
    """
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Fetch sentences without search vectors
        query = select(TranscriptSentence).where(TranscriptSentence.search_vector.is_(None))

        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        sentences_to_process = list(result.scalars().all())

        total_sentences = len(sentences_to_process)

        if total_sentences == 0:
            print("No transcript sentences found without search vectors.")
            return {
                "total": 0,
                "processed": 0,
            }

        print(f"Found {total_sentences} sentences without full-text search vectors")
        print(f"Generating vectors (no API calls)...")
        print()

        processed = 0
        batch_count = 0

        # Process in batches
        for i in range(0, total_sentences, batch_size):
            batch = sentences_to_process[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_sentences + batch_size - 1) // batch_size

            print(f"Processing batch {batch_num}/{total_batches}...")

            # Generate search vectors locally
            updates = []
            for sentence in batch:
                search_vector = to_tsvector("english", sentence.full_text)
                updates.append(
                    {
                        "sentence_id": sentence.sentence_id,
                        "search_vector": search_vector,
                    }
                )
                processed += 1

            # Batch update
            for update_data in updates:
                await session.execute(
                    update(TranscriptSentence)
                    .where(TranscriptSentence.sentence_id == update_data["sentence_id"])
                    .values(search_vector=update_data["search_vector"])
                )

            await session.commit()
            batch_count += 1

            # Progress
            progress = ((i + batch_size) / total_sentences) * 100
            progress = min(progress, 100)
            print(f"  Processed: {len(batch)}  Progress: {progress:.1f}%")
            print()

        print("=" * 60)
        print("Full-Text Vector Generation Complete!")
        print("=" * 60)
        print(f"Total sentences: {total_sentences}")
        print(f"Processed: {processed}")
        print(f"Batch count: {batch_count}")
        print()
        print("✓ Semantic search not available (run with --full-text-only for faster)")

        return {
            "total": total_sentences,
            "processed": processed,
            "batches": batch_count,
        }


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate embeddings for transcript sentences")
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only first N sentences (for testing)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of sentences to process per batch (default: 100)",
    )
    parser.add_argument(
        "--fulltext-only",
        action="store_true",
        help="Generate only full-text search vectors (no API calls, much faster)",
    )

    args = parser.parse_args()

    if args.fulltext_only:
        stats = await generate_only_fulltext_vectors(
            limit=args.limit,
            batch_size=args.batch_size,
        )
    else:
        stats = await generate_transcript_embeddings(
            limit=args.limit,
            batch_size=args.batch_size,
        )

    print()
    print("Summary:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
