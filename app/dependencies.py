"""Dependency injection utilities"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from core.database import get_db
from services.embeddings import EmbeddingService
from services.gemini import GeminiClient
from services.global_search import GlobalSearch
from services.local_search import LocalSearch
from services.parliamentary_agent import ParliamentaryAgent
from services.query_entity_extractor import QueryEntityExtractor
from storage.knowledge_graph_store import KnowledgeGraphStore


async def get_db_session() -> AsyncGenerator[AsyncSession]:
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


def get_embedding_service(
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> EmbeddingService:
    """Dependency for embedding service"""
    return EmbeddingService(gemini_client=gemini_client)


def get_query_entity_extractor(
    gemini_client: GeminiClient = Depends(get_gemini_client),
) -> QueryEntityExtractor:
    """Dependency for query entity extraction"""
    return QueryEntityExtractor(gemini_client=gemini_client)


def get_local_search(
    kg_store: KnowledgeGraphStore = Depends(get_knowledge_graph_store),
    entity_extractor: QueryEntityExtractor = Depends(get_query_entity_extractor),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> LocalSearch:
    """Dependency for local GraphRAG search"""
    return LocalSearch(
        kg_store=kg_store,
        entity_extractor=entity_extractor,
        embedding_service=embedding_service,
    )


def get_global_search(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> GlobalSearch:
    """Dependency for global GraphRAG search"""
    return GlobalSearch(embedding_service=embedding_service)


def get_parliamentary_agent(
    gemini_client: GeminiClient = Depends(get_gemini_client),
    kg_store: KnowledgeGraphStore = Depends(get_knowledge_graph_store),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    local_search: LocalSearch = Depends(get_local_search),
    global_search: GlobalSearch = Depends(get_global_search),
) -> ParliamentaryAgent:
    """Dependency for getting parliamentary agent"""
    return ParliamentaryAgent(
        gemini_client=gemini_client,
        kg_store=kg_store,
        local_search=local_search,
        global_search=global_search,
        embedding_service=embedding_service,
    )
