"""Tests for entity dedupe script helpers."""

import pytest
from sqlalchemy import select

from models.entity import Entity
from models.mention import Mention
from models.relationship import Relationship
from models.video import Video
from scripts import dedupe_entities


@pytest.mark.asyncio
async def test_apply_merge_plan_updates_references_and_deletes(db_session):
    survivor = Entity(
        entity_id="entity-a",
        entity_type="person",
        name="Jane Doe",
        canonical_name="Jane Doe",
        aliases=[],
        description="Minister",
        source="llm",
    )
    duplicate = Entity(
        entity_id="entity-b",
        entity_type="person",
        name="J. Doe",
        canonical_name="J. Doe",
        aliases=["J. Doe"],
        description=None,
        source="llm",
    )
    db_session.add_all([survivor, duplicate])
    await db_session.flush()

    video = Video(
        youtube_id="test123",
        youtube_url="https://youtube.com/watch?v=test123",
        title="Test Session",
    )
    db_session.add(video)
    await db_session.flush()

    mention = Mention(
        entity_id="entity-b",
        video_id=video.id,
    )
    relationship = Relationship(
        source_id="entity-b",
        target_id="entity-a",
        relation_type="mentions",
        sentiment="neutral",
        evidence="Mentioned in debate",
        source="derived",
    )
    db_session.add_all([mention, relationship])
    await db_session.flush()

    plan = dedupe_entities.MergePlan(
        actions=[
            dedupe_entities.MergeAction(
                survivor_id="entity-a",
                merge_ids=["entity-b"],
                confidence=0.93,
                reason="Same speaker name variant",
            )
        ]
    )

    await dedupe_entities.apply_merge_plan(db_session, plan)

    updated_mention = await db_session.scalar(select(Mention))
    updated_relationship = await db_session.scalar(select(Relationship))
    remaining_duplicate = await db_session.scalar(
        select(Entity).where(Entity.entity_id == "entity-b")
    )

    assert updated_mention.entity_id == "entity-a"
    assert updated_relationship.source_id == "entity-a"
    assert remaining_duplicate is None


def test_can_merge_entities_blocks_conflicting_speaker_ids():
    entity_a = Entity(
        entity_id="speaker-a",
        entity_type="person",
        name="Jane Doe",
        canonical_name="Jane Doe",
        aliases=[],
        description=None,
        source="llm",
        speaker_canonical_id="speaker-a",
    )
    entity_b = Entity(
        entity_id="speaker-b",
        entity_type="person",
        name="Jane Doe",
        canonical_name="Jane Doe",
        aliases=[],
        description=None,
        source="llm",
        speaker_canonical_id="speaker-b",
    )

    assert dedupe_entities.can_merge_entities(entity_a, entity_b) is False
