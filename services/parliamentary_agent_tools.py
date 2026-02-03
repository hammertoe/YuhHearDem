"""Parliamentary agent tools for function calling"""

from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from storage.knowledge_graph_store import KnowledgeGraphStore


class ParliamentaryAgentTools:
    """Tool functions that the parliamentary agent can use."""

    def __init__(self, knowledge_store: KnowledgeGraphStore):
        """Initialize tools with knowledge graph store.

        Args:
            knowledge_store: Knowledge graph storage layer
        """
        self.kg_store = knowledge_store

    async def find_entity(
        self,
        db: AsyncSession,
        name: str,
        entity_type: Optional[str] = None,
    ) -> dict:
        """
        Tool: Find entities by name or type.

        Returns:
            Tool response for Gemini
        """
        entity = await self.kg_store.find_entity(db, name, entity_type)

        if entity:
            return {
                "status": "success",
                "data": {
                    "entities": [entity],
                    "total": 1,
                },
            }
        else:
            return {
                "status": "error",
                "error": f"Entity '{name}' not found. Try being more specific or check the entity type.",
            }

    async def get_relationships(
        self,
        db: AsyncSession,
        entity_id: str,
        direction: str = "all",
    ) -> dict:
        """
        Tool: Get relationships for an entity.

        Args:
            db: Database session
            entity_id: Entity ID
            direction: Direction filter ('incoming', 'outgoing', 'all')

        Returns:
            Tool response for Gemini
        """
        relationships = await self.kg_store.get_relationships(db, entity_id, direction)

        return {
            "status": "success",
            "data": {
                "relationships": relationships,
                "total": len(relationships),
            },
        }

    async def get_mentions(
        self,
        db: AsyncSession,
        entity_id: str,
        video_id: Optional[str] = None,
        limit: int = 10,
    ) -> dict:
        """
        Tool: Get mentions of an entity with timestamps.

        Args:
            db: Database session
            entity_id: Entity ID
            video_id: Optional video filter
            limit: Maximum mentions to return

        Returns:
            Tool response for Gemini
        """
        mentions = await self.kg_store.get_mentions(db, entity_id, video_id, limit)

        return {
            "status": "success",
            "data": {
                "mentions": mentions,
                "total": len(mentions),
            },
        }

    async def get_entity_details(
        self,
        db: AsyncSession,
        entity_id: str,
    ) -> dict:
        """
        Tool: Get full entity details.

        Args:
            db: Database session
            entity_id: Entity ID

        Returns:
            Tool response for Gemini
        """
        entity = await self.kg_store.get_entity_details(db, entity_id)

        if entity:
            return {
                "status": "success",
                "data": {
                    "entity": entity,
                    "metadata": {
                        "aliases": entity.get("aliases", []),
                        "importance_score": entity.get("importance_score", 0),
                    },
                },
            }
        else:
            return {
                "status": "error",
                "error": f"Entity '{entity_id}' not found.",
            }

    async def search_by_date_range(
        self,
        db: AsyncSession,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        chamber: Optional[str] = None,
    ) -> dict:
        """
        Tool: Search for sessions within date range.

        Args:
            db: Database session
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            chamber: Filter by chamber

        Returns:
            Tool response for Gemini
        """
        videos = await self.kg_store.search_by_date_range(
            db, date_from, date_to, chamber
        )

        return {
            "status": "success",
            "data": {
                "sessions": videos,
                "total": len(videos),
            },
        }

    async def search_by_speaker(
        self,
        db: AsyncSession,
        speaker_id: str,
    ) -> dict:
        """
        Tool: Find all videos where this speaker appears.

        Args:
            db: Database session
            speaker_id: Speaker canonical ID

        Returns:
            Tool response for Gemini
        """
        videos = await self.kg_store.search_by_speaker(db, speaker_id)

        return {
            "status": "success",
            "data": {
                "videos": videos,
                "total": len(videos),
            },
        }

    async def search_semantic(
        self,
        db: AsyncSession,
        query_text: str,
        limit: int = 10,
    ) -> dict:
        """
        Tool: Semantic search over transcript sentences.

        Args:
            db: Database session
            query_text: Search query text
            limit: Maximum results

        Returns:
            Tool response for Gemini
        """
        results = await self.kg_store.search_semantic(db, query_text, limit)

        return {
            "status": "success",
            "data": {
                "results": results,
                "total": len(results),
            },
        }

    def get_tools_dict(self) -> Dict[str, callable]:
        """
        Get all tools as dictionary for Gemini function calling.

        Returns:
            Dictionary of tool_name → tool_function
        """
        return {
            "find_entity": lambda db, **kwargs: self.find_entity(db, **kwargs),
            "get_relationships": lambda db, **kwargs: self.get_relationships(
                db, **kwargs
            ),
            "get_mentions": lambda db, **kwargs: self.get_mentions(db, **kwargs),
            "get_entity_details": lambda db, **kwargs: self.get_entity_details(
                db, **kwargs
            ),
            "search_by_date_range": lambda db, **kwargs: self.search_by_date_range(
                db, **kwargs
            ),
            "search_by_speaker": lambda db, **kwargs: self.search_by_speaker(
                db, **kwargs
            ),
            "search_semantic": lambda db, **kwargs: self.search_semantic(db, **kwargs),
        }
