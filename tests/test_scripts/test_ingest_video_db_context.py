"""Ingest video database session helpers."""

from contextlib import asynccontextmanager

import pytest

from scripts import ingest_video


class DummySession:
    """Dummy async session placeholder."""

    async def close(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_db_session_context_uses_session_maker(monkeypatch):
    """Context manager should yield from get_session_maker."""

    @asynccontextmanager
    async def _dummy_session():
        yield DummySession()

    def _dummy_session_maker():
        return _dummy_session()

    monkeypatch.setattr(ingest_video, "get_session_maker", lambda: _dummy_session_maker)

    async with ingest_video._db_session() as session:
        assert isinstance(session, DummySession)
