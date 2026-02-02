"""Parliamentary agent service - agentic RAG with function calling"""

from typing import Optional, Dict, List
from services.gemini import GeminiClient


class ParliamentaryAgent:
    """Agentic system for querying parliamentary knowledge graph with function calling."""

    def __init__(self, gemini_client: GeminiClient):
        """Initialize agent with Gemini client.

        Args:
            gemini_client: Gemini client for function calling
        """
        self.client = gemini_client

    def query(self, user_query: str, tools: Dict[str, callable]) -> Dict:
        """
        Process a natural language query using agentic reasoning.

        Args:
            user_query: User's natural language question
            tools: Dictionary of tool_name → tool_function mappings

        Returns:
            Structured response with citations
        """
        # Build agent prompt with tool definitions
        prompt = self._build_agent_prompt(user_query, tools)

        # Create function calling configuration
        tools_config = self._create_tools_config(tools)

        # Generate response with function calling
        response = self._call_gemini_with_tools(prompt, tools_config)

        return self._parse_agent_response(response)

    def _build_agent_prompt(self, query: str, tools: Dict[str, callable]) -> str:
        """Build prompt for agentic query processing."""
        tools_description = "\n".join(
            [
                f"  - {name}: {desc}"
                for name, desc in [
                    ("find_entity", "Search for entities by name or type"),
                    ("get_relationships", "Get relationships between entities"),
                    (
                        "get_mentions",
                        "Get where entities are mentioned with timestamps",
                    ),
                ]
            ]
        )

        return f"""You are an AI assistant for the Barbados Parliament knowledge graph. Your role is to help users query parliamentary sessions, find information about legislation, and understand relationships between speakers and topics.

Available Tools:
{tools_description}

Instructions:
1. Understand the user's question and break it down into smaller steps if needed.
2. Use the appropriate tools to gather information.
3. Synthesize information from multiple tools.
4. Provide clear, well-structured answers.
5. Always cite your sources with video IDs, timestamps, and direct quotes.
6. If you cannot find information, say so rather than making things up.

User Question: {query}

Think through your approach step by step:
1. Which tools do you need to call first?
2. What information are you looking for?
3. How can you best answer the user's question?
4. What evidence should you provide?

Begin your analysis and response."""

    def _create_tools_config(self, tools: Dict[str, callable]) -> dict:
        """Create tools configuration for Gemini function calling."""
        function_declarations = []
        for name, func in tools.items():
            function_declarations.append(
                {
                    "name": name,
                    "description": func.__doc__
                    if hasattr(func, "__doc__")
                    else f"Tool: {name}",
                }
            )

        return {
            "function_declarations": function_declarations,
        }

    def _call_gemini_with_tools(self, prompt: str, tools_config: dict) -> dict:
        """Call Gemini with function calling configuration."""
        try:
            response = self.client.models.generate_content(
                model="gemini-2-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.FunctionDeclaration(**decl)
                        for decl in tools_config["function_declarations"]
                    ]
                ),
            )
            return response.json()
        except Exception as e:
            return {
                "error": str(e),
                "success": False,
            }

    def _parse_agent_response(self, response: dict) -> Dict:
        """Parse Gemini response into structured format."""
        if "error" in response:
            return {
                "success": False,
                "error": response["error"],
                "answer": None,
                "sources": [],
                "tool_calls": [],
            }

        tool_calls = response.get("function_calls", [])
        if not tool_calls:
            return {
                "success": True,
                "answer": "I couldn't find relevant information in the knowledge graph for your query. The knowledge graph may need more data. Please try rephrasing your question or check that videos have been processed.",
                "sources": [],
                "tool_calls": [],
            }

        answer_parts = []
        sources = []

        for call in tool_calls:
            tool_name = call.get("name", "")
            function_result = call.get("response", {})
            if function_result:
                answer_parts.append(f"\n**Tool: {tool_name}**\n{function_result}")
                sources.extend(self._extract_sources(function_result))

        answer = "\n\n".join(answer_parts)

        return {
            "success": True,
            "answer": answer,
            "sources": sources,
            "tool_calls": tool_calls,
        }

    def _extract_sources(self, function_result: dict) -> List[dict]:
        """Extract source citations from function results."""
        sources = []

        if "entities" in function_result:
            for entity in function_result.get("entities", []):
                sources.append(
                    {
                        "type": "entity",
                        "id": entity.get("entity_id"),
                        "name": entity.get("name"),
                        "description": entity.get("description", ""),
                    }
                )

        if "relationships" in function_result:
            for rel in function_result.get("relationships", []):
                sources.append(
                    {
                        "type": "relationship",
                        "source_id": rel.get("source_id"),
                        "target_id": rel.get("target_id"),
                        "relation_type": rel.get("relation_type"),
                        "evidence": rel.get("evidence", ""),
                    }
                )

        if "mentions" in function_result:
            for mention in function_result.get("mentions", []):
                sources.append(
                    {
                        "type": "mention",
                        "entity_id": mention.get("entity_id"),
                        "video_id": mention.get("video_id", ""),
                        "timestamp": mention.get("timestamp", ""),
                        "context": mention.get("context", ""),
                    }
                )

        return sources
