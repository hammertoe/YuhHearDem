"""Tests for HybridGraphRAG neighborhood expansion."""

import pytest

from models.entity import Entity
from models.relationship import Relationship
from services.hybrid_graphrag import HybridGraphRAG


@pytest.mark.anyio
async def test_expand_neighborhood_returns_relationships_without_recursion_error(
    db_session,
):
    entity_a = Entity(
        entity_id="entity-a-001",
        entity_type="place",
        name="Entity A",
        canonical_name="entity a",
    )
    entity_b = Entity(
        entity_id="entity-b-001",
        entity_type="place",
        name="Entity B",
        canonical_name="entity b",
    )
    relationship = Relationship(
        source_id=entity_a.entity_id,
        target_id=entity_b.entity_id,
        relation_type="mentions",
        evidence="Entity A mentions Entity B.",
        confidence=0.9,
        source="test",
    )

    db_session.add_all([entity_a, entity_b, relationship])
    await db_session.commit()

    rag = HybridGraphRAG(kg_store=None, entity_extractor=None, embedding_service=None)
    result = await rag._expand_neighborhood(db_session, [entity_a.entity_id], max_hops=1)

    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["source_id"] == entity_a.entity_id
    assert result["relationships"][0]["target_id"] == entity_b.entity_id
    assert "path_names" in result["relationships"][0]
