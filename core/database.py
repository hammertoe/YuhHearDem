"""Database connection and session management"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import get_settings

Base = declarative_base()

_engine: create_async_engine | None = None
_async_session_maker: async_sessionmaker | None = None


def get_engine():
    """Get or create database engine"""
    global _engine, _async_session_maker
    if _engine is None:
        settings = get_settings()

        # SQLite doesn't support pool_size and max_overflow
        engine_kwargs = {
            "echo": settings.debug,
        }
        if "postgresql" in settings.database_url:
            engine_kwargs["pool_size"] = settings.database_pool_size
            engine_kwargs["max_overflow"] = settings.database_max_overflow

        _engine = create_async_engine(settings.database_url, **engine_kwargs)
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _engine


def get_session_maker():
    """Get or create async session maker"""
    get_engine()
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency for getting async database sessions"""
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables (for development only)"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None


def reset_engine():
    """Reset engine for testing"""
    global _engine, _async_session_maker
    _engine = None
    _async_session_maker = None
