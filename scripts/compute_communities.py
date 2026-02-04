#!/usr/bin/env python3
"""Compute communities for GraphRAG."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from services.community_detection import CommunityDetection
from services.community_summarizer import CommunitySummarizer
from services.gemini import GeminiClient


async def main() -> None:
    parser = argparse.ArgumentParser(description="Compute communities for GraphRAG")
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate LLM summaries for each community",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=1.0,
        help="Community detection resolution (default: 1.0)",
    )
    args = parser.parse_args()

    settings = get_settings()

    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as db:
        print("Detecting communities...")

        detector = CommunityDetection(resolution=args.resolution)
        communities = await detector.compute_and_save(db)

        print(f"Detected {len(communities)} communities")

        stats = await detector.get_community_stats(db)
        print("\nCommunity statistics:")
        print(f"  Total communities: {stats['total_communities']}")
        print(f"  Total entities: {stats['total_entities']}")
        print(f"  Average community size: {stats['avg_community_size']:.1f}")
        print(f"  Largest community: {stats['largest_community']} entities")
        print(f"  Smallest community: {stats['smallest_community']} entities")

        if args.summarize:
            print("\nGenerating community summaries...")

            gemini_client = GeminiClient(api_key=settings.google_api_key)
            summarizer = CommunitySummarizer(gemini_client=gemini_client)

            summaries = await summarizer.compute_and_save_all(db)

            print(f"Generated {len(summaries)} summaries")

            print("\nSample summaries:")
            for summary in summaries[:3]:
                print(f"\nCommunity {summary['community_id']}: {summary['primary_focus']}")
                print(f"Summary: {summary['summary'][:100]}...")
                print(f"Themes: {', '.join(summary.get('key_themes', [])[:3])}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
