"""Tests for transcript segment model types."""

from sqlalchemy import JSON
from sqlalchemy.dialects import sqlite

from models.transcript_segment import EmbeddingVector


def test_embedding_vector_uses_json_for_sqlite():
    """SQLite should store embeddings as JSON."""
    dialect = sqlite.dialect()
    impl = EmbeddingVector().load_dialect_impl(dialect)

    assert isinstance(impl, JSON)
