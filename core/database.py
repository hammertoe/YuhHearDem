"""Database connection and session management."""

from collections.abc import AsyncGenerator
from threading import Lock
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy models."""


class DatabaseManager:
    """Singleton manager for database engine and session maker."""

    _instance: "DatabaseManager | None" = None
    _lock: Lock = Lock()

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._async_session_maker: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_engine(self) -> AsyncEngine:
        """Get or create database engine."""
        if self._engine is None:
            settings = get_settings()

            if "postgresql" in settings.database_url:
                engine_kwargs: dict[str, Any] = {
                    "echo": settings.debug,
                    "pool_size": settings.database_pool_size,
                    "max_overflow": settings.database_max_overflow,
                }
            else:
                engine_kwargs = {"echo": settings.debug}

            self._engine = create_async_engine(settings.database_url, **engine_kwargs)
            self._async_session_maker = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        return self._engine

    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """Get or create async session maker."""
        self.get_engine()
        if self._async_session_maker is None:
            raise RuntimeError("Session maker not initialized")
        return self._async_session_maker

    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._async_session_maker = None

    def reset(self) -> None:
        """Reset cached engine/session maker."""
        self._engine = None
        self._async_session_maker = None


_db_manager = DatabaseManager.get_instance()


def get_engine() -> AsyncEngine:
    """Get or create database engine."""
    return _db_manager.get_engine()


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get or create async session maker."""
    return _db_manager.get_session_maker()


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


async def reset_db() -> None:
    """Drop and recreate all tables"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    await _db_manager.close()


def reset_engine() -> None:
    """Reset cached engine/session maker"""
    _db_manager.reset()
