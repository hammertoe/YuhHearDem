"""Pytest configuration and fixtures"""

import asyncio
import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Default test database URL (PostgreSQL with pgvector)
DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/yuhheardem_test"


@pytest.fixture(autouse=True, scope="session")
def set_test_database():
    """Set test database URL before any imports"""
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = DEFAULT_TEST_DATABASE_URL
    if not os.environ.get("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = "test"
    # Clear cached settings to force reload

    get_settings.cache_clear()


from app.config import get_settings
from core.database import Base, reset_engine


@pytest.fixture(scope="function")
async def db_engine():
    """Create test database engine"""
    from sqlalchemy import text
    from sqlalchemy.pool import StaticPool

    database_url = os.environ.get("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    engine_kwargs: dict = {"echo": False}

    if database_url.startswith("sqlite"):
        engine_kwargs.update(
            {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        )
    else:
        engine_kwargs["poolclass"] = NullPool

    engine = create_async_engine(database_url, **engine_kwargs)

    async with engine.begin() as conn:
        if not database_url.startswith("sqlite"):
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        if not database_url.startswith("sqlite"):
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
def override_get_db(db_engine):
    """Override get_db dependency for testing"""

    async def _get_test_db():
        session_maker = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

        async with session_maker() as session:
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
    """Create async test client"""
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from app.dependencies import get_db_session
    from app.main import app

    app.dependency_overrides[get_db_session] = override_get_db

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
