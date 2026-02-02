"""Dependency injection utilities"""

from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from app.config import get_settings


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async for session in get_db():
        yield session


def get_config():
    """Dependency for getting application config"""
    return get_settings()
