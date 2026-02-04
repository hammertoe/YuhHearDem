"""Query entity extractor for GraphRAG.

Extracts entities from user queries using Gemini LLM, enabling the system
to map natural language questions to knowledge graph entities.
"""

from dataclasses import dataclass

from services.gemini import GeminiClient


@dataclass
class QueryEntity:
    """Entity extracted from a user query."""

    name: str
    entity_type: str | None = None
    confidence: float = 1.0


class QueryEntityExtractor:
    """Extract entities from natural language queries using Gemini."""

    # Schema for structured entity extraction
    ENTITY_EXTRACTION_SCHEMA = {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "description": "Entities mentioned in the user query",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The exact name or phrase as it appears in the query",
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": [
                                "person",
                                "organization",
                                "place",
                                "law",
                                "concept",
                                "event",
                                "bill",
                                "committee",
                                "policy",
                                "unknown",
                            ],
                            "description": "The type of entity",
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence that this is a real entity in the query",
                        },
                    },
                    "required": ["name"],
                },
            }
        },
        "required": ["entities"],
    }

    def __init__(self, gemini_client: GeminiClient):
        """Initialize extractor.

        Args:
            gemini_client: Gemini client for LLM calls
        """
        self.client = gemini_client

    def extract(self, query: str) -> list[QueryEntity]:
        """Extract entities from a user query.

        Uses Gemini with structured output to identify entities mentioned
        in natural language questions.

        Args:
            query: User's natural language question

        Returns:
            List of extracted entities with types and confidence scores
        """
        if not query or not query.strip():
            return []

        prompt = f"""Extract all entities mentioned in this query about Barbados parliamentary proceedings.

Query: "{query}"

Identify specific people (Senators, MPs, Ministers), organizations, bills, laws, places, and key concepts mentioned.

Return entities even if:
- Names are partial (e.g., "Cummins" instead of full "Senator Lisa Cummins")
- Entities are referenced indirectly (e.g., "the Transport Bill" instead of full bill name)
- Concepts are implied by context

Examples:
Query: "What did Senator Cummins say about CARICOM?"
→ Entities: [{{"name": "Senator Cummins", "type": "person"}}, {{"name": "CARICOM", "type": "organization"}}]

Query: "When was the Transport Bill discussed?"
→ Entities: [{{"name": "Transport Bill", "type": "bill"}}]

Query: "Tell me about education funding"
→ Entities: [{{"name": "education funding", "type": "concept"}}]
"""

        try:
            response = self.client.generate_structured(
                prompt=prompt,
                response_schema=self.ENTITY_EXTRACTION_SCHEMA,
            )

            if not response or "entities" not in response:
                return []

            entities = []
            for entity_data in response["entities"]:
                entity = QueryEntity(
                    name=entity_data.get("name", "").strip(),
                    entity_type=entity_data.get("entity_type"),
                    confidence=entity_data.get("confidence", 1.0),
                )
                if entity.name:  # Only add if name is not empty
                    entities.append(entity)

            return entities

        except Exception as e:
            # Log error but return empty list rather than crash
            print(f"Error extracting entities from query: {e}")
            return []

    def extract_with_types(
        self,
        query: str,
        allowed_types: list[str] | None = None,
    ) -> list[QueryEntity]:
        """Extract entities filtered by type.

        Args:
            query: User's natural language question
            allowed_types: Optional list of entity types to include

        Returns:
            Filtered list of entities
        """
        entities = self.extract(query)

        if allowed_types:
            entities = [e for e in entities if e.entity_type in allowed_types]

        return entities
