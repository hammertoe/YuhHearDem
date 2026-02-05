"""Tests for HybridGraphRAG mention handling."""

import pytest

from models.entity import Entity
from models.mention import Mention
from models.video import Video
from services.hybrid_graphrag import HybridGraphRAG


@pytest.mark.anyio
async def test_get_mentions_for_entities_returns_expected_fields(db_session):
    entity = Entity(
        entity_id="pothole-entity-001",
        entity_type="concept",
        name="Potholes",
        canonical_name="potholes",
    )
    video = Video(
        youtube_id="abc123",
        youtube_url="https://youtube.com/watch?v=abc123",
        title="House Sitting",
        chamber="house",
    )
    db_session.add_all([entity, video])
    await db_session.flush()

    mention = Mention(
        entity_id=entity.entity_id,
        video_id=video.id,
        timestamp_seconds=123,
        context="Discussion about potholes.",
        speaker_id="speaker-001",
        segment_id="seg-001",
    )

    db_session.add(mention)
    await db_session.commit()

    rag = HybridGraphRAG(kg_store=None, entity_extractor=None, embedding_service=None)
    mentions = await rag._get_mentions_for_entities(db_session, [entity.entity_id])

    assert entity.entity_id in mentions
    assert mentions[entity.entity_id][0]["timestamp"] == 123
    assert "confidence" not in mentions[entity.entity_id][0]
