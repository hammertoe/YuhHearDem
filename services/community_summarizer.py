"""Community summarization service for GraphRAG."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.community import CommunitySummary, EntityCommunity
from models.entity import Entity
from models.mention import Mention
from models.transcript_segment import TranscriptSegment
from services.gemini import GeminiClient


@dataclass
class CommunityContext:
    """Context information for a community."""

    community_id: int
    member_entities: list[dict]
    sample_segments: list[dict]
    total_mentions: int


class CommunitySummarizer:
    """Generate summaries for communities using LLM."""

    SUMMARY_SCHEMA = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_themes": {"type": "array", "items": {"type": "string"}},
            "primary_focus": {"type": "string"},
        },
        "required": ["summary", "key_themes", "primary_focus"],
    }

    def __init__(
        self,
        gemini_client: GeminiClient,
        max_segments_per_community: int = 10,
    ):
        self.client = gemini_client
        self.max_segments = max_segments_per_community

    async def summarize_community(
        self,
        db: AsyncSession,
        community_id: int,
    ) -> dict[str, Any] | None:
        context = await self._get_community_context(db, community_id)
        if not context:
            return None

        prompt = self._build_summary_prompt(context)

        try:
            response = self.client.generate_structured(
                prompt=prompt,
                response_schema=self.SUMMARY_SCHEMA,
                stage="community_summarization",
            )

            return {
                "community_id": community_id,
                "summary": response.get("summary", ""),
                "key_themes": response.get("key_themes", []),
                "primary_focus": response.get("primary_focus", ""),
                "member_count": len(context.member_entities),
                "sample_segments_count": len(context.sample_segments),
            }

        except Exception as e:
            print(f"Error summarizing community {community_id}: {e}")
            return None

    async def summarize_all_communities(
        self,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(EntityCommunity.community_id).distinct()
        )
        community_ids = [row[0] for row in result.all()]

        summaries = []
        for community_id in community_ids:
            summary = await self.summarize_community(db, community_id)
            if summary:
                summaries.append(summary)

        return summaries

    async def save_summaries(
        self,
        db: AsyncSession,
        summaries: list[dict[str, Any]],
    ) -> None:
        for summary_data in summaries:
            result = await db.execute(
                select(CommunitySummary).where(
                    CommunitySummary.community_id == summary_data["community_id"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.summary = summary_data["summary"]
                existing.key_entities = summary_data.get("key_themes", [])
                existing.member_count = summary_data.get("member_count", 0)
            else:
                db.add(CommunitySummary(
                    community_id=summary_data["community_id"],
                    summary=summary_data["summary"],
                    key_entities=summary_data.get("key_themes", []),
                    member_count=summary_data.get("member_count", 0),
                ))

        await db.commit()

    async def compute_and_save_all(
        self,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        summaries = await self.summarize_all_communities(db)
        await self.save_summaries(db, summaries)
        return summaries

    async def _get_community_context(
        self,
        db: AsyncSession,
        community_id: int,
    ) -> CommunityContext | None:
        result = await db.execute(
            select(Entity)
            .join(EntityCommunity, Entity.entity_id == EntityCommunity.entity_id)
            .where(EntityCommunity.community_id == community_id)
        )
        entities = result.scalars().all()

        if not entities:
            return None

        member_entities = [
            {
                "entity_id": e.entity_id,
                "name": e.name,
                "type": e.entity_type,
                "description": e.description,
            }
            for e in entities
        ]

        entity_ids = [e.entity_id for e in entities]

        result = await db.execute(
            select(TranscriptSegment, Mention)
            .join(Mention, TranscriptSegment.segment_id == Mention.segment_id)
            .where(Mention.entity_id.in_(entity_ids))
            .limit(self.max_segments)
        )

        rows = result.all()
        sample_segments = [
            {
                "text": row.TranscriptSegment.text,
                "speaker_id": row.TranscriptSegment.speaker_id,
                "entity_id": row.Mention.entity_id,
                "context": row.Mention.context,
            }
            for row in rows
        ]

        result = await db.execute(
            select(Mention)
            .where(Mention.entity_id.in_(entity_ids))
        )
        total_mentions = len(result.scalars().all())

        return CommunityContext(
            community_id=community_id,
            member_entities=member_entities,
            sample_segments=sample_segments,
            total_mentions=total_mentions,
        )

    def _build_summary_prompt(self, context: CommunityContext) -> str:
        entities_text = "\n".join([
            f"- {e['name']} ({e['type']}): {e.get('description', 'No description')[:100]}"
            for e in context.member_entities[:20]
        ])

        segments_text = "\n\n".join([
            f"Segment {i+1}:\n{s['text'][:300]}..."
            for i, s in enumerate(context.sample_segments[:5])
        ])

        return f"""Analyze this community of entities from Barbados parliamentary proceedings and generate a summary.

COMMUNITY STATISTICS:
- Total member entities: {len(context.member_entities)}
- Total mentions in transcripts: {context.total_mentions}

MEMBER ENTITIES:
{entities_text}

SAMPLE DISCUSSION SEGMENTS:
{segments_text}

Based on these entities and discussion segments, what is this community about? What are the key themes, topics, and focus areas?
"""
