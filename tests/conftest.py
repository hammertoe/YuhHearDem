"""Pytest configuration and fixtures"""

import asyncio
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from core.database import Base, get_db
from app.config import get_settings

# Test database URL (using sqlite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def db_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
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
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session_maker = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
def override_get_db(db_session):
    """Override get_db dependency for testing"""

    def _get_test_db():
        yield db_session

    return _get_test_db


@pytest.fixture(scope="function")
async def client(override_get_db):
    """Create test FastAPI client"""
    from fastapi.testclient import TestClient
    from app.main import app

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
