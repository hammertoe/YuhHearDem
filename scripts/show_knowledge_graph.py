#!/usr/bin/env python3
"""Show knowledge graph from test video"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session_maker


async def show_knowledge_graph():
    session_maker = get_session_maker()

    async with session_maker() as db:
        # Get video details
        from models.video import Video

        video_result = await db.execute(select(Video).where(Video.youtube_id == "P6cUJb9xqIs"))
        video = video_result.scalar_one_or_none()

        if video:
            print("=" * 80)
            print("VIDEO DETAILS")
            print("=" * 80)
            print(f"Title: {video.title}")
            print(f"URL: {video.youtube_url}")
            print()

            if video.transcript:
                transcript = video.transcript
                print(f"Session Title: {transcript.get('session_title', 'N/A')}")
                print(f"Date: {transcript.get('date', 'N/A')}")
                print(f"Chamber: {transcript.get('chamber', 'N/A')}")
                print(f"Agenda Items: {len(transcript.get('agenda_items', []))}")

                print()
                print("=" * 80)
                print("TRANSCRIPT SAMPLE")
                print("=" * 80)
                for i, agenda in enumerate(transcript.get("agenda_items", [])[:3], 1):
                    print(f"\n{i}. {agenda.get('topic_title', 'Unknown')}")
                    for block in agenda.get("speech_blocks", [])[:2]:
                        print(f"   Speaker: {block.get('speaker_name', 'Unknown')}")
                        for sentence in block.get("sentences", [])[:2]:
                            print(
                                f"     - [{sentence.get('start_time', '?')}] {sentence.get('text', '')[:80]}..."
                            )

        # Get entities
        print()
        print("=" * 80)
        print("EXTRACTED ENTITIES")
        print("=" * 80)
        from models.entity import Entity

        entities_result = await db.execute(
            select(Entity)
            .where(Entity.source_ref.like("%P6cUJb9xqIs%"))
            .order_by(Entity.importance_score.desc())
        )
        entities = entities_result.scalars().all()
        print(f"Total entities: {len(entities)}\n")

        for entity in entities[:10]:
            print(f"  [{entity.entity_type}] {entity.name}")
            print(f"    Canonical: {entity.canonical_name}")
            if entity.description:
                print(
                    f"    Description: {entity.description[:100]}..."
                    if len(entity.description) > 100
                    else f"    Description: {entity.description}"
                )
            print(
                f"    Score: {entity.importance_score:.2f} | Confidence: {entity.entity_confidence:.2f}"
            )
            print()

        if len(entities) > 10:
            print(f"  ... and {len(entities) - 10} more entities")

        # Get relationships
        print()
        print("=" * 80)
        print("ENTITY RELATIONSHIPS")
        print("=" * 80)
        from models.relationship import Relationship

        rels_result = await db.execute(
            select(Relationship).where(Relationship.source_ref.like("%P6cUJb9xqIs%")).limit(10)
        )
        rels = rels_result.scalars().all()
        print(f"Total relationships: {len(rels)}\n")

        for rel in rels:
            print(f"  {rel.relation_type}")
            print(f"    {rel.source_id} -> {rel.target_id}")
            print(
                f"    Evidence: {rel.evidence[:100]}..."
                if len(rel.evidence) > 100
                else f"    Evidence: {rel.evidence}"
            )
            print(f"    Confidence: {rel.confidence:.2f}")
            print()


if __name__ == "__main__":
    asyncio.run(show_knowledge_graph())
