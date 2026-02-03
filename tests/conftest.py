"""Pytest configuration and fixtures"""

import asyncio
import os
import pytest
import tempfile
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Test database URL (using sqlite file for tests)
# Using a file instead of :memory: to allow shared database access
TEST_DATABASE_URL = "sqlite+aiosqlite:///"


@pytest.fixture(autouse=True, scope="session")
def set_test_database():
    """Set test database URL before any imports"""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    # Clear cached settings to force reload
    from app.config import get_settings

    get_settings.cache_clear()


from core.database import Base
from app.config import get_settings


@pytest.fixture(scope="function")
async def db_engine():
    """Create test database engine"""
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db").name
    test_db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session_maker(db_engine):
    """Create test database session maker"""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db_session(db_session_maker):
    """Create test database session"""
    async with db_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
def override_get_db(db_session_maker):
    """Override get_db dependency for testing"""

    async def _get_test_db():
        async with db_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    return _get_test_db


@pytest.fixture(scope="function")
async def client(override_get_db):
    """Create test FastAPI client"""
    from fastapi.testclient import TestClient
    from app.main import app
    from core.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
