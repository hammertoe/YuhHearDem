"""Pytest configuration and fixtures"""

import asyncio
import os
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Test database URL (using PostgreSQL with pgvector)
TEST_DATABASE_URL = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/yuhheardem_test"
)


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
    from sqlalchemy import text

    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.run_sync(Base.metadata.create_all)

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


@pytest.fixture(scope="session", autouse=True)
def verify_postgres():
    """Verify PostgreSQL is running before tests"""
    from sqlalchemy import create_engine, text

    engine = create_engine("postgresql://postgres:postgres@localhost:5432/postgres")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}. Run 'docker-compose up' first.")
    finally:
        engine.dispose()
