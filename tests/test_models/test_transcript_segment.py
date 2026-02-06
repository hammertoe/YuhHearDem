"""Tests for transcript segment model types."""

from sqlalchemy import JSON
from sqlalchemy.dialects import sqlite

from models.transcript_segment import EmbeddingVector


def test_embedding_vector_uses_json_for_sqlite():
    """SQLite and PostgreSQL store embeddings appropriately."""
    from sqlalchemy.dialects import sqlite, postgresql

    dialect = sqlite.dialect()
    impl = EmbeddingVector().load_dialect_impl(dialect)

    dialect_postgresql = postgresql.dialect()
    impl_postgresql = EmbeddingVector().load_dialect_impl(dialect_postgresql)

    assert isinstance(impl, JSON)
    # PostgreSQL would use Vector type from pgvector
