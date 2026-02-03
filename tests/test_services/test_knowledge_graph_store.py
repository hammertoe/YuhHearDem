"""Knowledge graph storage layer tests"""

import pytest

from storage.knowledge_graph_store import KnowledgeGraphStore


@pytest.mark.skip(
    "TODO: Rewrite with proper Entity model including canonical_name and other required fields"
)
class TestKnowledgeGraphStore:
    """Test knowledge graph storage."""

    async def test_find_entity_none_found(self, db_session):
        """Test find_entity when no entity matches"""
        store = KnowledgeGraphStore()

        result = await store.find_entity(db_session, "nonexistent", "person")

        assert result is None

    async def test_find_entity_by_name(self, db_session):
        """Test find_entity by exact name"""
        pytest.skip("Entity model requires canonical_name field")

    async def test_find_entity_by_partial_name(self, db_session):
        """Test find_entity by partial name"""
        pytest.skip("Entity model requires canonical_name field")

    async def test_find_entity_with_type_filter(self, db_session):
        """Test find_entity filters by type"""
        pytest.skip("Entity model requires canonical_name field")

    async def test_get_relationships_empty(self, db_session):
        """Test get_relationships returns empty list when entity has no relationships"""
        pytest.skip("Entity model requires canonical_name field")

    async def test_get_relationships_outgoing(self, db_session):
        """Test get_relationships returns outgoing relationships"""
        pytest.skip("Entity and Relationship models have different field requirements")
