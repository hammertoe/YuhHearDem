"""Parliamentary agent - Complete implementation with multi-hop reasoning"""

from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession

from services.gemini import GeminiClient
from services.parliamentary_agent_tools import ParliamentaryAgentTools
from storage.knowledge_graph_store import KnowledgeGraphStore


class ParliamentaryAgent:
    """Complete parliamentary agent with agentic reasoning and multi-hop queries."""

    def __init__(self, gemini_client: GeminiClient, kg_store: KnowledgeGraphStore):
        """Initialize complete agent.

        Args:
            gemini_client: Gemini client for function calling
            kg_store: Knowledge graph storage layer
        """
        self.client = gemini_client
        self.kg_store = kg_store
        self.tools = ParliamentaryAgentTools(kg_store)

    async def query(
        self,
        db: AsyncSession,
        user_query: str,
        max_iterations: int = 10,
    ) -> dict:
        """
        Process a natural language query using multi-hop agentic reasoning.

        Args:
            db: Database session
            user_query: User's natural language question
            max_iterations: Maximum agent iterations

        Returns:
            Structured response with citations and entities
        """
        iteration = 0
        context = []

        entities_found = []

        while iteration < max_iterations:
            iteration += 1

            prompt = self._build_agent_prompt(user_query, context, iteration, max_iterations)
            tools_dict = self.tools.get_tools_dict()

            response = await self.client.client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.FunctionDeclaration(**decl)
                        for decl in tools_dict["function_declarations"]
                    ]
                ),
            )

            response_text = response.text
            if response_text is None:
                response_text = ""

            result = self._parse_agent_response(response_text, user_query)

            if result["success"]:
                # Extract entities found during this iteration
                entities = self._extract_entities_from_result(result)
                entities_found.extend(entities)

                # Extract context for next iteration
                context = self._extract_context_from_response(result)

                return {
                    "success": True,
                    "answer": result.get("answer", ""),
                    "entities": entities_found,
                    "context": context,
                    "iteration": iteration,
                }
            else:
                # Error occurred
                return {
                    "success": False,
                    "error": "An error occurred: " + result.get("error", ""),
                    "answer": None,
                    "entities": entities_found,
                    "context": context,
                    "iteration": iteration,
                }

        return {
            "success": False,
            "error": "Max iterations reached without a successful response",
            "answer": None,
            "entities": entities_found,
            "context": context,
            "iteration": iteration,
        }

    def _build_agent_prompt(
        self, user_query: str, context: list[str], iteration: int, max_iterations: int
    ) -> str:
        """Build prompt for agent iteration."""
        context_info = ""
        tools_info = ""
        if iteration > 1:
            context_info = "\n\nPrevious research:"

            tools_info = "\nAvailable tools:\n" + "\n".join(
                [
                    "  - find_entity(name, type): Search entities by name or type",
                    "  - get_relationships(entity_id, direction): Get entity connections",
                    "  - get_mentions(entity_id, video_id, limit): Get citations with timestamps",
                    "  - get_entity_details(entity_id): Full entity metadata",
                    "  - search_by_date_range(date_from, date_to, chamber): Find sessions",
                    "  - search_by_speaker(speaker_id): Find all speeches",
                    "  - search_semantic(query_text, limit): Semantic search",
                ]
            )

        return f"""You are an AI assistant for the Barbados Parliament knowledge graph. Use the available tools to answer the user's question comprehensively.

{context_info}
{tools_info}

User Question: {user_query}

Instructions:
1. Break down complex questions into smaller steps.
2. Use the most appropriate tools for each step.
3. Chain multiple tool calls together (e.g., find_entity → get_relationships → get_mentions).
4. Synthesize information from all tools before answering.
5. Provide specific, well-supported answers with citations.
6. Always include: video IDs, timestamps, and direct quotes.
7. If information is missing, clearly state that.

Current iteration: {iteration}/{max_iterations}

Think step by step:
- What is the user asking for?
- Which tools should you call first?
- What information do you need to gather?
- How should you structure your final answer?
- What evidence will support your claims?

Begin your analysis."""

    def _parse_agent_response(self, response_text: str, user_query: str) -> dict:
        """Parse Gemini response into structured format."""
        if "function_calls" in response_text:
            return self._parse_function_calls(response_text, user_query)
        else:
            return {
                "success": False,
                "error": "Response format not recognized",
                "answer": None,
                "context": [],
                "iteration": 0,
            }

    def _parse_function_calls(self, response_text: str, user_query: str) -> dict:
        """Parse function call blocks from response."""
        import json

        tool_results = []
        lines = response_text.split("\n")

        current_tool = None
        current_data_lines: list[str] = []

        for line in lines:
            if line.startswith("Tool: "):
                if current_tool and current_data_lines:
                    try:
                        data = json.loads("\n".join(current_data_lines))
                        tool_results[-1]["data"].update(data)
                    except json.JSONDecodeError:
                        pass

                tool_name = line[6:].strip()
                current_tool = tool_name
                tool_results.append({"tool": current_tool, "data": {}})
                current_data_lines = []
                continue

            if line.startswith("Data: "):
                if line.strip() == "Data: {}":
                    current_data_lines = []
                    continue

                data_str = line[6:].strip()
                if data_str:
                    current_data_lines = [data_str]
                continue

            if current_tool and line.startswith("    "):
                current_data_lines.append(line[4:])

        if current_tool and current_data_lines:
            try:
                data = json.loads("\n".join(current_data_lines))
                tool_results[-1]["data"].update(data)
            except json.JSONDecodeError:
                pass

        return {
            "success": True,
            "answer": self._generate_answer_from_results(tool_results, user_query),
            "context": [],
            "iteration": 0,
            "tool_results": tool_results,
        }

    def _extract_context_from_response(self, result: dict) -> list[str]:
        """Extract context for next iteration."""
        context = []

        for tool_result in result.get("tool_results", []):
            tool = tool_result["tool"]

            if tool == "find_entity" and tool_result["data"]:
                entity = tool_result["data"].get("entities", [{}])
                context.append(f"Found entity: {entity.get('name', 'Unknown')}")
                if entity:
                    context.append(f"  Entity type: {entity.get('entity_type', 'Unknown')}")

            elif tool == "get_relationships" and tool_result["data"]:
                relationships = tool_result["data"].get("relationships", [])
                context.append(f"Found {len(relationships)} relationships")

            elif tool == "get_mentions" and tool_result["data"]:
                mentions = tool_result["data"].get("mentions", [])
                context.append(f"Found {len(mentions)} mentions")

        return context

    def _extract_entities_from_result(self, result: dict) -> list[dict]:
        """Extract entities from tool results."""
        entities = []

        for tool_result in result.get("tool_results", []):
            tool = tool_result["tool"]
            data = tool_result.get("data")

            if tool == "find_entity" and data:
                entity_data = data.get("entities", [])
                if entity_data and len(entity_data) > 0:
                    entity = entity_data[0]
                    entities.append(
                        {
                            "entity_id": entity.get("entity_id", ""),
                            "name": entity.get("name", ""),
                            "type": entity.get("entity_type", ""),
                        }
                    )

        return entities

    def _generate_answer_from_results(self, tool_results: list[dict], user_query: str) -> str:
        """Generate final answer from tool results."""
        if not tool_results:
            return "I couldn't find relevant information to answer your question. The knowledge graph may need more data. Please try rephrasing or check that videos have been processed."

        answer_parts = ["Based on the available data:"]

        entities_mentioned = []
        relationships_found = []
        mentions_with_timestamps = []

        for tool_result in tool_results:
            tool = tool_result["tool"]
            data = tool_result["data"]

            if tool == "find_entity" and data.get("entities"):
                entity = data.get("entities", [{}])
                if entity:
                    entities_mentioned.append(
                        f"- {entity['name']} (Type: {entity.get('entity_type', 'Unknown')})"
                    )

            elif tool == "get_relationships" and data.get("relationships"):
                relationships = data.get("relationships", [])
                for rel in relationships:
                    relationships_found.append(
                        f"- Relationship between {rel.get('source_id', 'Unknown')} and {rel.get('target_id', 'Unknown')}"
                    )

            elif tool == "get_mentions" and data.get("mentions"):
                mentions = data.get("mentions", [])
                for m in mentions:
                    timestamp = m.get("timestamp", "0")
                    if timestamp:
                        mentions_with_timestamps.append(
                            f"- Mention at {timestamp}s ({m.get('context', '')})"
                        )

        if not entities_mentioned and not relationships_found:
            answer_parts.append(
                "No specific entities or relationships found in the knowledge graph for your query."
            )
        elif not entities_mentioned:
            answer_parts.append(
                f"I found the following entities: {', '.join(entities_mentioned)}. Try asking about these directly."
            )
        elif relationships_found:
            answer_parts.append(
                f"I found {len(relationships_found)} relationships between entities."
            )

        if mentions_with_timestamps:
            answer_parts.append("\n**Citations:**")
            for m in mentions_with_timestamps[:5]:
                answer_parts.append(f"- {m.get('context', '')} (at {m.get('timestamp', '0')}s)")

        answer_parts.append(
            "\n\nNote: For more detailed information about any entity, use the get_entity_details tool."
        )

        return "\n\n".join(answer_parts)

    def format_answer_with_citations(self, answer: str, citations: list[dict]) -> str:
        """Format answer with citations."""
        if not citations:
            return answer

        sections = []
        current_section = ""

        def add_section(title: str) -> None:
            nonlocal current_section
            if current_section != title:
                if current_section:
                    sections.append(current_section)
                current_section = title

        add_section("Answer")

        for citation in citations:
            cite_type = citation.get("type", "mention")

            if cite_type == "mention" and citation.get("timestamp"):
                add_section(f"Citation at {citation.get('timestamp', '0')}s")
                if citation.get("context"):
                    add_section(f'Context: "{citation.get("context", "")}"')
                    if citation.get("video_id"):
                        add_section(
                            f"Source: https://youtube.com/watch?v={citation.get('video_id', '')}"
                        )
            elif cite_type == "relationship":
                source_entity_id = citation.get("source_id", "Unknown")
                target_entity_id = citation.get("target_id", "Unknown")
                relation = citation.get("relation_type", "Unknown")
                add_section(f"Relationship: {source_entity_id} → {target_entity_id} ({relation})")

            if citation.get("evidence"):
                add_section(f'"{citation.get("evidence", "")}"')

        sections.append("\n")

        return "\n".join(sections)
