"""Query entity extractor for GraphRAG."""

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

    ENTITY_EXTRACTION_SCHEMA = {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
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
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "required": ["name"],
                },
            }
        },
        "required": ["entities"],
    }

    def __init__(self, gemini_client: GeminiClient):
        self.client = gemini_client

    def extract(self, query: str) -> list[QueryEntity]:
        """Extract entities from a user query."""
        if not query or not query.strip():
            return []

        prompt = f"""Extract entities mentioned in this query about Barbados parliamentary proceedings.

Query: "{query}"

IMPORTANT - Extract ONLY specific entities the user is asking about:
- Ignore generic terms like "Barbados" when it appears in the prompt context but is not the actual focus of the user's question
- Focus on what the user specifically wants to know about (topics, people, bills, organizations)
- Only extract "Barbados" if the user explicitly asks about Barbados itself

Identify specific people, organizations, bills, laws, places, and key concepts mentioned.

Return entities even if:
- Names are partial (e.g., "Cummins" instead of full "Senator Lisa Cummins")
- Entities are referenced indirectly
- Concepts are implied by context
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
                if entity.name:
                    entities.append(entity)

            return entities

        except Exception as e:
            print(f"Error extracting entities from query: {e}")
            return []

    def extract_with_types(
        self,
        query: str,
        allowed_types: list[str] | None = None,
    ) -> list[QueryEntity]:
        """Extract entities filtered by type."""
        entities = self.extract(query)

        if allowed_types:
            entities = [e for e in entities if e.entity_type in allowed_types]

        return entities
