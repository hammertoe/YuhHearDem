"""Dependency injection utilities"""

from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from app.config import get_settings
from services.gemini import GeminiClient
from services.parliamentary_agent import ParliamentaryAgent
from storage.knowledge_graph_store import KnowledgeGraphStore


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async for session in get_db():
        yield session


def get_config():
    """Dependency for getting application config"""
    return get_settings()


def get_gemini_client() -> GeminiClient:
    """Dependency for getting Gemini client"""
    settings = get_settings()
    return GeminiClient(api_key=settings.google_api_key)


def get_knowledge_graph_store() -> KnowledgeGraphStore:
    """Dependency for getting knowledge graph store"""
    return KnowledgeGraphStore()


def get_parliamentary_agent(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    kg_store: KnowledgeGraphStore = Depends(get_knowledge_graph_store),
) -> ParliamentaryAgent:
    """Dependency for getting parliamentary agent"""
    return ParliamentaryAgent(gemini_client=gemini_client, kg_store=kg_store)
