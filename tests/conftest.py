"""Pytest configuration and fixtures"""

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Test database URL (using PostgreSQL with pgvector)
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/yuhheardem_test"


@pytest.fixture(autouse=True, scope="session")
def set_test_database():
    """Set test database URL before any imports"""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    # Clear cached settings to force reload

    get_settings.cache_clear()


from app.config import get_settings
from core.database import Base, reset_engine


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
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()


@pytest.fixture(autouse=True, scope="function")
def reset_db_engine():
    """Reset cached engine between tests"""
    reset_engine()
    yield
    reset_engine()


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
def override_get_db():
    """Override get_db dependency for testing"""

    async def _get_test_db():
        engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
            echo=False,
        )
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
                await engine.dispose()

    return _get_test_db


@pytest.fixture(scope="function")
async def client(override_get_db):
    """Create async test client"""
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from core.database import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend():
    """Limit anyio to asyncio backend"""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def verify_postgres():
    """Verify PostgreSQL is running before tests"""
    import asyncpg

    async def _check():
        conn = await asyncpg.connect(
            user="postgres",
            password="postgres",
            database="postgres",
            host="localhost",
            port=5432,
        )
        await conn.execute("SELECT 1")
        await conn.close()

    try:
        asyncio.run(_check())
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}. Run 'docker-compose up' first.")


@pytest.fixture
def mock_db():
    """Mock database session for testing"""
    from unittest.mock import AsyncMock

    from sqlalchemy.ext.asyncio import AsyncSession

    mock = AsyncMock(spec=AsyncSession)
    mock.execute = AsyncMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.refresh = AsyncMock()
    return mock
