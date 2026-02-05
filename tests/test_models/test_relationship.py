"""Tests for relationship model defaults."""

import pytest

from models.relationship import Relationship


@pytest.mark.asyncio
async def test_relationship_defaults_source_when_missing(db_session):
    """Relationships should default source when not provided."""
    relationship = Relationship(
        source_id="entity-1",
        target_id="entity-2",
        relation_type="supports",
        sentiment=None,
        evidence="The senator strongly supported this bill",
        confidence=0.9,
        source_ref=None,
        video_id=None,
        timestamp_seconds=0,
    )

    db_session.add(relationship)
    await db_session.commit()
    await db_session.refresh(relationship)

    assert relationship.source == "unknown"
