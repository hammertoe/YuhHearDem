"""Ingest video database session helpers."""

import pytest

from scripts import ingest_video


class DummySession:
    """Dummy async session placeholder."""


@pytest.mark.asyncio
async def test_db_session_context_uses_get_db(monkeypatch):
    """Context manager should yield from get_db."""

    async def _dummy_get_db():
        yield DummySession()

    monkeypatch.setattr(ingest_video, "get_db", _dummy_get_db)

    async with ingest_video._db_session() as session:
        assert isinstance(session, DummySession)
