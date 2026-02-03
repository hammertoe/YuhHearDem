"""Storage layer tests"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import select

from models.entity import Entity
from storage.knowledge_graph_store import KnowledgeGraphStore
from api.schemas import QueryRequest


class TestKnowledgeGraphStore:
    """Test knowledge graph storage."""

    async def test_find_entity_not_found(self, mock_db):
        """Test find_entity when entity not found."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        store = KnowledgeGraphStore()

        entity_id = "test-entity"
        entity = Entity(entity_id=entity_id, name="Test Entity", entity_type="organization")

        result = await store.find_entity(mock_db, entity_id)

        assert result is None
        mock_db.execute.assert_awaited_with(
            select(text).where(Entity.entity_id == entity_id)
        )

    async def test_find_entity_found(self, mock_db):
        """Test find_entity when entity exists."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        store = KnowledgeGraphStore()

        entity_id = "test-entity"
        entity = Entity(entity_id=entity_id, name="Test Entity", entity_type="organization")

        result = await store.find_entity(mock_db, entity_id)

        assert result is not None
        mock_db.execute.assert_awaited_with(
            select(text).where(Entity.entity_id == entity_id)
        )

    async def test_get_relationships_no_relations(self, mock_db):
        """Test get_relationships when entity has no relationships."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        store = KnowledgeGraphStore()

        entity_id = "test-entity"
        entity = Entity(entity_id=entity_id, name="Test Entity", entity_type="organization")

        result = await store.get_relationships(mock_db, entity_id)

        assert result == {"relationships": [], "total": 0}
        mock_db.execute.assert_awaited_with(
            select(text).where(Entity.entity_id == entity_id)
        )

    async def test_get_mentions_empty(self, mock_db):
        """Test get_mentions when entity has no mentions."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        store = KnowledgeGraphStore()

        entity_id = "test-entity"
        entity = Entity(entity_id=entity_id, name="Test Entity", entity_type="organization")

        result = await store.get_mentions(mock_db, entity_id)

        assert result == {"mentions": [], "total": 0}
        mock_db.execute.assert_awaited_with(
            select(text).where(Entity.entity_id == entity_id)
        )

    async def test_search_by_date_range(self, mock_db):
        """Test search by date range."""
        from datetime import datetime
        from storage.knowledge_graph_store import KnowledgeGraphStore

        store = KnowledgeGraphStore()

        date_from = "2024-01-01"
        date_to = "2024-01-31"
        result = await store.search_by_date_range(
            mock_db, date_from, date_to
        )

        assert result["total"] == 1
        mock_db.execute.assert_awaited_with(
            select(text).where(Video.session_date.between(date_from, date_to))
        )

    async def test_search_by_speaker(self, mock_db):
        """Test search by speaker."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        speaker_id = "test-speaker"

        result = await store.search_by_speaker(mock_db, speaker_id)

        assert result["total"] == 1
        mock_db.execute.assert_awaited_with(
            select(text).where(Video.transcript["speakers"].contains(speaker_id))
        )

    async def test_search_semantic(self, mock_db):
        """Test semantic search."""
        from sqlalchemy import text
        from storage.knowledge_graph_store import KnowledgeGraphStore

        query_text = "test query"

        result = await store.search_semantic(mock_db, query_text)

        assert result["total"] == 1
        mock_db.execute.assert_q_awaited_with(
            select(text).order_by(VectorEmbedding.embedding.cosine_similarity(query_text), 0.7).limit(10)
        )
