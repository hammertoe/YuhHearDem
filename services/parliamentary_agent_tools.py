"""Parliamentary agent tools for function calling"""

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
        entity_type: str | None = None,
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
        video_id: str | None = None,
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
        date_from: str | None = None,
        date_to: str | None = None,
        chamber: str | None = None,
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
        videos = await self.kg_store.search_by_date_range(db, date_from, date_to, chamber)

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

    def get_tools_dict(self) -> dict[str, callable]:
        """
        Get tools for Gemini function calling.

        Returns:
            Dictionary with function declarations and tool callables
        """
        return {
            "function_declarations": self._get_function_declarations(),
            "tools": {
                "find_entity": lambda db, **kwargs: self.find_entity(db, **kwargs),
                "get_relationships": lambda db, **kwargs: self.get_relationships(db, **kwargs),
                "get_mentions": lambda db, **kwargs: self.get_mentions(db, **kwargs),
                "get_entity_details": lambda db, **kwargs: self.get_entity_details(db, **kwargs),
                "search_by_date_range": lambda db, **kwargs: self.search_by_date_range(
                    db, **kwargs
                ),
                "search_by_speaker": lambda db, **kwargs: self.search_by_speaker(db, **kwargs),
                "search_semantic": lambda db, **kwargs: self.search_semantic(db, **kwargs),
            },
        }

    def _get_function_declarations(self) -> list[dict]:
        """Define tool function declarations for Gemini."""
        return [
            {
                "name": "find_entity",
                "description": "Find entities by name or type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "entity_type": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "get_relationships",
                "description": "Get relationships for an entity.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "direction": {
                            "type": "string",
                            "enum": ["incoming", "outgoing", "all"],
                        },
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "get_mentions",
                "description": "Get mentions of an entity with timestamps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                        "video_id": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "get_entity_details",
                "description": "Get full entity details.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string"},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "search_by_date_range",
                "description": "Search for sessions within a date range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "chamber": {"type": "string"},
                    },
                },
            },
            {
                "name": "search_by_speaker",
                "description": "Find all videos where a speaker appears.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "speaker_id": {"type": "string"},
                    },
                    "required": ["speaker_id"],
                },
            },
            {
                "name": "search_semantic",
                "description": "Semantic search over transcript sentences.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_text": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query_text"],
                },
            },
        ]
