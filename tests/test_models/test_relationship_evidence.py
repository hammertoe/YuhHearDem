"""Test relationship_evidence model"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from core.database import Base, get_engine
from models.relationship_evidence import RelationshipEvidence
from models.relationship import Relationship
from models.transcript_segment import TranscriptSegment
from models.video import Video
from models.session import Session as SessionModel
from models.speaker import Speaker
from models.entity import Entity


@pytest.mark.asyncio
async def test_relationship_evidence_links_to_segment(db_session):
    """Test that relationship_evidence references a specific transcript segment"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    video = Video(
        video_id="Syxyah7QIaM",
        session_id="s_125_2026_01_06",
        platform="youtube",
        url="https://www.youtube.com/watch?v=Syxyah7QIaM",
        duration_seconds=3600,
    )
    db_session.add(video)
    await db_session.flush()

    speaker = Speaker(
        speaker_id="p_bradshaw",
        name="John Bradshaw",
        title="Honourable",
        role="Member of Parliament",
        chamber="house",
        aliases=[],
    )
    db_session.add(speaker)
    await db_session.flush()

    segment = TranscriptSegment(
        segment_id="Syxyah7QIaM_00395",
        session_id="s_125_2026_01_06",
        video_id="Syxyah7QIaM",
        speaker_id="p_bradshaw",
        start_time_seconds=395,
        end_time_seconds=420,
        text="We also have accompanying Road Traffic Act...",
        speech_block_index=0,
        segment_index=0,
    )
    db_session.add(segment)
    await db_session.flush()

    entity1 = Entity(
        entity_id="bill_road_traffic_2025",
        name="Road Traffic (Amendment) Bill 2025",
        canonical_name="Road Traffic (Amendment) Bill 2025",
        entity_type="Legislation",
        entity_subtype="Bill",
        description="Bill to update road safety regulations",
        aliases=["Road Traffic Bill"],
        importance_score=0.5,
        source="test",
        source_ref="s_125_2026_01_06",
    )
    entity2 = Entity(
        entity_id="act_295",
        name="Road Traffic Act 295",
        canonical_name="Road Traffic Act 295",
        entity_type="Legislation",
        entity_subtype="Act",
        description="Primary road safety legislation",
        aliases=["Traffic Act"],
        importance_score=0.5,
        source="test",
        source_ref="s_125_2026_01_06",
    )
    db_session.add(entity1)
    db_session.add(entity2)
    await db_session.flush()

    relationship = Relationship(
        relationship_id=uuid.uuid4(),
        source_entity_id="bill_road_traffic_2025",
        target_entity_id="act_295",
        relation="AMENDS",
        description="Updates safety regulations",
        source="test",
        source_ref="s_125_2026_01_06",
        confidence=0.9,
    )
    db_session.add(relationship)
    await db_session.flush()

    evidence = RelationshipEvidence(
        evidence_id=uuid.uuid4(),
        relationship_id=relationship.relationship_id,
        segment_id="Syxyah7QIaM_00395",
        video_id="Syxyah7QIaM",
        start_time_seconds=395,
    )
    db_session.add(evidence)
    await db_session.commit()

    result = await db_session.execute(select(RelationshipEvidence))
    fetched = result.scalar_one()

    assert fetched is not None
    assert fetched.segment_id == "Syxyah7QIaM_00395"
    assert fetched.video_id == "Syxyah7QIaM"
    assert fetched.start_time_seconds == 395
    assert fetched.relationship_id == relationship.relationship_id


@pytest.mark.asyncio
async def test_relationship_evidence_multiple_segments(db_session):
    """Test that one relationship can have multiple evidence segments"""
    session = SessionModel(
        session_id="s_125_2026_01_06",
        date=datetime(2026, 1, 6).date(),
        title="House of Assembly Sitting",
        sitting_number="125",
        chamber="house",
    )
    db_session.add(session)
    await db_session.flush()

    video = Video(
        video_id="Syxyah7QIaM",
        session_id="s_125_2026_01_06",
        platform="youtube",
        url="https://www.youtube.com/watch?v=Syxyah7QIaM",
        duration_seconds=3600,
    )
    db_session.add(video)
    await db_session.flush()

    speaker = Speaker(
        speaker_id="p_bradshaw",
        name="John Bradshaw",
        title="Honourable",
        role="Member of Parliament",
        chamber="house",
        aliases=[],
    )
    db_session.add(speaker)
    await db_session.flush()

    entity1 = Entity(
        entity_id="bill_road_traffic_2025",
        name="Road Traffic (Amendment) Bill 2025",
        canonical_name="Road Traffic (Amendment) Bill 2025",
        entity_type="Legislation",
        entity_subtype="Bill",
        description="Bill to update road safety regulations",
        aliases=["Road Traffic Bill"],
        importance_score=0.5,
        source="test",
        source_ref="s_125_2026_01_06",
    )
    entity2 = Entity(
        entity_id="act_295",
        name="Road Traffic Act 295",
        canonical_name="Road Traffic Act 295",
        entity_type="Legislation",
        entity_subtype="Act",
        description="Primary road safety legislation",
        aliases=["Traffic Act"],
        importance_score=0.5,
        source="test",
        source_ref="s_125_2026_01_06",
    )
    db_session.add(entity1)
    db_session.add(entity2)
    await db_session.flush()

    segment1 = TranscriptSegment(
        segment_id="Syxyah7QIaM_00395",
        session_id="s_125_2026_01_06",
        video_id="Syxyah7QIaM",
        speaker_id="p_bradshaw",
        start_time_seconds=395,
        end_time_seconds=420,
        text="We also have accompanying Road Traffic Act...",
        speech_block_index=0,
        segment_index=0,
    )
    segment2 = TranscriptSegment(
        segment_id="Syxyah7QIaM_01250",
        session_id="s_125_2026_01_06",
        video_id="Syxyah7QIaM",
        speaker_id="p_bradshaw",
        start_time_seconds=1250,
        end_time_seconds=1300,
        text="The amendments strengthen safety provisions...",
        speech_block_index=1,
        segment_index=1,
    )
    db_session.add(segment1)
    db_session.add(segment2)
    await db_session.flush()

    relationship = Relationship(
        relationship_id=uuid.uuid4(),
        source_entity_id="bill_road_traffic_2025",
        target_entity_id="act_295",
        relation="AMENDS",
        description="Updates safety regulations",
        source="test",
        source_ref="s_125_2026_01_06",
        confidence=0.9,
    )
    db_session.add(relationship)
    await db_session.flush()

    evidence1 = RelationshipEvidence(
        evidence_id=uuid.uuid4(),
        relationship_id=relationship.relationship_id,
        segment_id="Syxyah7QIaM_00395",
        video_id="Syxyah7QIaM",
        start_time_seconds=395,
    )
    evidence2 = RelationshipEvidence(
        evidence_id=uuid.uuid4(),
        relationship_id=relationship.relationship_id,
        segment_id="Syxyah7QIaM_01250",
        video_id="Syxyah7QIaM",
        start_time_seconds=1250,
    )
    db_session.add(evidence1)
    db_session.add(evidence2)
    await db_session.commit()

    result = await db_session.execute(
        select(RelationshipEvidence).where(
            RelationshipEvidence.relationship_id == relationship.relationship_id
        )
    )
    fetched = result.scalars().all()

    assert len(fetched) == 2
    assert all(e.relationship_id == relationship.relationship_id for e in fetched)
