"""Parliamentary agent - Complete implementation with multi-hop reasoning"""

from typing import Any

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
        context: list[str] = []

        entities_found: list[dict] = []

        while iteration < max_iterations:
            iteration += 1

            prompt = self._build_agent_prompt(user_query, context, iteration, max_iterations)
            tools_dict = self.tools.get_tools_dict()
            latest_tool_results: list[dict] = []

            if self._is_latest_session_query(user_query):
                latest = await self.tools.get_latest_session(db=db)
                if latest.get("status") == "success":
                    latest_tool_results = [
                        {"tool": "get_latest_session", "data": latest.get("data", {})}
                    ]

            gemini_tools = [
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(**decl)
                        for decl in tools_dict["function_declarations"]
                    ]
                )
            ]

            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                )
            ]

            response = await self._call_llm(contents, gemini_tools)
            response, circuit_broken, last_tool_results = await self._execute_tool_loop(
                response,
                contents,
                gemini_tools,
                tools_dict.get("tools", {}),
                db,
            )

            if circuit_broken:
                fallback_answer = None
                if last_tool_results:
                    fallback_answer = self._generate_answer_from_results(
                        last_tool_results, user_query
                    )
                return {
                    "success": True,
                    "answer": fallback_answer
                    or "I got a bit confused there. Could you try rephrasing that?",
                    "entities": entities_found,
                    "context": context,
                    "iteration": iteration,
                }

            response_text = response.text or ""
            if not response_text and last_tool_results:
                response_text = self._generate_answer_from_results(last_tool_results, user_query)

            if self._is_latest_session_query(user_query) and not last_tool_results:
                latest = await self.tools.get_latest_session(db=db)
                if latest.get("status") == "success":
                    response_text = self._generate_answer_from_results(
                        [{"tool": "get_latest_session", "data": latest.get("data", {})}],
                        user_query,
                    )

            result = self._parse_agent_response(response_text, user_query)

            if last_tool_results and not result.get("tool_results"):
                result["tool_results"] = last_tool_results

            force_with_results = None
            if latest_tool_results:
                answer_text = result.get("answer", "") if result.get("success") else ""
                if self._should_force_latest_answer(answer_text, latest_tool_results):
                    force_with_results = latest_tool_results

            if (
                not force_with_results
                and last_tool_results
                and self._is_latest_session_query(user_query)
            ):
                latest_result = next(
                    (r for r in last_tool_results if r.get("tool") == "get_latest_session"),
                    None,
                )
                if latest_result:
                    answer_text = result.get("answer", "") if result.get("success") else ""
                    if self._should_force_latest_answer(answer_text, [latest_result]):
                        force_with_results = [latest_result]

            if force_with_results:
                forced_entities = self._extract_entities_from_result(
                    {"tool_results": force_with_results, "success": True}
                )
                result = {
                    "success": True,
                    "answer": self._generate_answer_from_results(force_with_results, user_query),
                    "context": [],
                    "iteration": 0,
                    "tool_results": force_with_results,
                    "entities": forced_entities,
                }

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
                if result.get("error") == "Response format not recognized":
                    return {
                        "success": True,
                        "answer": (
                            "I couldn't find enough information to answer that right now. "
                            "Please try rephrasing or ask about a specific session, speaker, or topic."
                        ),
                        "entities": entities_found,
                        "context": context,
                        "iteration": iteration,
                    }

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
                    "  - get_latest_session(chamber): Latest session with highlights",
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
7. If the user asks about the last or latest session, call get_latest_session first and include at least one exact quote in double quotes.
8. If information is missing, clearly state that.

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

        if response_text.strip():
            return {
                "success": True,
                "answer": response_text.strip(),
                "context": [],
                "iteration": 0,
                "tool_results": [],
            }

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

        tool_results: list[dict[str, Any]] = []
        lines = response_text.split("\n")

        current_tool = None
        current_data_lines: list[str] = []

        for line in lines:
            if line.startswith("Tool: "):
                if current_tool and current_data_lines:
                    try:
                        data = json.loads("\n".join(current_data_lines))
                        if isinstance(data, dict):
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
                if isinstance(data, dict):
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

    async def _call_llm(
        self,
        contents: list[types.Content],
        gemini_tools: list[types.Tool],
    ) -> types.GenerateContentResponse:
        """Call Gemini with the provided contents and tools."""
        return await self.client.client.aio.models.generate_content(
            model=self.client.model,
            contents=contents,
            config=types.GenerateContentConfig(tools=gemini_tools),  # type: ignore[arg-type]
        )

    def _get_function_calls(self, response: types.GenerateContentResponse) -> list:
        """Extract function calls from Gemini response parts."""
        function_calls = []
        candidates = getattr(response, "candidates", []) or []

        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", []) or []
            for part in parts:
                function_call = getattr(part, "function_call", None)
                if function_call:
                    function_calls.append(function_call)

        return function_calls

    async def _execute_tool_loop(
        self,
        response: types.GenerateContentResponse,
        contents: list[types.Content],
        gemini_tools: list[types.Tool],
        tools: dict,
        db: AsyncSession,
        max_tool_iterations: int = 5,
    ) -> tuple[types.GenerateContentResponse, bool, list[dict]]:
        """Execute tool calls in a loop until none remain."""
        function_calls = self._get_function_calls(response)
        last_tool_results: list[dict] = []
        iteration = 0

        while function_calls:
            iteration += 1
            if iteration > max_tool_iterations:
                return response, True, last_tool_results

            tool_results, tool_response_parts = await self._execute_tool_calls(
                db=db,
                calls=function_calls,
                tools=tools,
            )

            last_tool_results = tool_results

            candidate_content = None
            candidates = getattr(response, "candidates", []) or []
            if candidates:
                candidate_content = getattr(candidates[0], "content", None)

            if not candidate_content:
                return response, False, last_tool_results

            contents.append(candidate_content)

            contents.append(types.Content(role="user", parts=tool_response_parts))

            response = await self._call_llm(contents, gemini_tools)
            function_calls = self._get_function_calls(response)

        return response, False, last_tool_results

    async def _execute_tool_calls(
        self,
        db: AsyncSession,
        calls: list,
        tools: dict,
    ) -> tuple[list[dict], list[types.Part]]:
        """Execute tool calls and return results and response parts."""
        results: list[dict] = []
        response_parts: list[types.Part] = []

        for call in calls:
            tool_name = getattr(call, "name", None) or "unknown_tool"
            tool_args = getattr(call, "args", {}) or {}
            tool_fn = tools.get(tool_name)

            if not tool_fn:
                error_payload = {
                    "status": "error",
                    "error": f"Unknown tool: {tool_name}",
                }
                results.append({"tool": tool_name, "data": error_payload})
                response_parts.append(
                    types.Part.from_function_response(name=tool_name, response=error_payload)
                )
                continue

            tool_response = await tool_fn(db, **tool_args)
            if not isinstance(tool_response, dict):
                tool_response = {"status": "error", "error": "Tool response not a dict"}

            results.append({"tool": tool_name, "data": tool_response.get("data", {})})
            response_parts.append(
                types.Part.from_function_response(name=tool_name, response=tool_response)
            )

        return results, response_parts

    def _extract_context_from_response(self, result: dict) -> list[str]:
        """Extract context for next iteration."""
        context = []

        for tool_result in result.get("tool_results", []):
            tool = tool_result["tool"]

            if tool == "find_entity" and tool_result["data"]:
                entities = tool_result["data"].get("entities", [])
                entity = entities[0] if entities else {}
                context.append(f"Found entity: {entity.get('name', 'Unknown')}")
                if entity:
                    context.append(f"  Entity type: {entity.get('entity_type', 'Unknown')}")

            elif tool == "get_relationships" and tool_result["data"]:
                relationships = tool_result["data"].get("relationships", [])
                context.append(f"Found {len(relationships)} relationships")

            elif tool == "get_mentions" and tool_result["data"]:
                mentions = tool_result["data"].get("mentions", [])
                context.append(f"Found {len(mentions)} mentions")

            elif tool == "get_latest_session" and tool_result["data"]:
                title = tool_result["data"].get("title", "Latest session")
                date = tool_result["data"].get("session_date", "Unknown date")
                context.append(f"Latest session: {title} ({date})")

        return context

    def _is_latest_session_query(self, user_query: str) -> bool:
        """Detect if the user is asking about the latest session."""
        query = user_query.lower()
        return "last session" in query or "latest session" in query

    def _should_force_latest_answer(self, answer_text: str, tool_results: list[dict]) -> bool:
        """Determine if we should override with latest session tool data."""
        if not answer_text.strip():
            return True

        latest_data = tool_results[0].get("data", {}) if tool_results else {}
        topics = [t.lower() for t in latest_data.get("topics", []) if isinstance(t, str)]
        quotes = [q.lower() for q in latest_data.get("quotes", []) if isinstance(q, str)]

        answer_lower = answer_text.lower()
        has_topic = any(topic in answer_lower for topic in topics)
        has_quote = any(quote in answer_lower for quote in quotes)

        return not (has_topic or has_quote)

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
                entities = data.get("entities", [])
                entity = entities[0] if entities else {}
                if entity:
                    entities_mentioned.append(
                        f"- {entity['name']} (Type: {entity.get('entity_type', 'Unknown')})"
                    )

            if tool == "get_latest_session" and data:
                session_title = data.get("title") or "Latest session"
                session_date = data.get("session_date") or "Unknown date"
                topics = data.get("topics", [])
                quotes = data.get("quotes", [])

                answer_parts.append(f"Latest session: {session_title} ({session_date}).")
                if topics:
                    answer_parts.append("Topics discussed:")
                    answer_parts.extend([f"- {topic}" for topic in topics])
                if quotes:
                    answer_parts.append("Notable quotes:")
                    answer_parts.extend([f'"{quote}"' for quote in quotes[:2]])

            elif tool in ("search_by_date_range", "search_by_speaker") and data.get("sessions"):
                videos = data.get("sessions", [])
                if videos:
                    answer_parts.append(f"Found {len(videos)} session(s):")
                    for video in videos:
                        title = video.get("title", "Unknown session")
                        date = (
                            video.get("session_date", "Unknown date")[:10]
                            if isinstance(video.get("session_date"), str)
                            else video.get("session_date")
                        )
                        answer_parts.append(f"\n{title} ({date})")

                        transcript = video.get("transcript", {})
                        if transcript.get("agenda_items"):
                            answer_parts.append("Topics discussed:")
                            for item in transcript.get("agenda_items", [])[:3]:
                                topic = item.get("topic_title", "")
                                if topic:
                                    answer_parts.append(f"- {topic}")

                            for item in transcript.get("agenda_items", [])[:2]:
                                for block in item.get("speech_blocks", [])[:2]:
                                    for sentence in block.get("sentences", [])[:2]:
                                        text = sentence.get("text", "")
                                        if text and len(answer_parts) < 15:
                                            answer_parts.append(f'"{text}"')
                                            break
                                    if len(answer_parts) >= 15:
                                        break
                                if len(answer_parts) >= 15:
                                    break
                            if len(answer_parts) >= 15:
                                break

            elif tool == "search_semantic" and data.get("results"):
                results = data.get("results", [])
                if results:
                    answer_parts.append(f"Found {len(results)} relevant segment(s):")
                    for result in results[:3]:
                        text = result.get("text", "")
                        video_title = result.get("video_title", "Unknown video")
                        if text:
                            answer_parts.append(f"\nFrom {video_title}:")
                            answer_parts.append(f'"{text}"')
                            timestamp = result.get("timestamp")
                            if timestamp:
                                answer_parts.append(f"Timestamp: {timestamp}s")
                        if len(answer_parts) >= 15:
                            break

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
            answer_parts.extend(mentions_with_timestamps[:5])

        answer_parts.append(
            "\n\nNote: For more detailed information about any entity, use the get_entity_details tool."
        )

        return "\n\n".join(answer_parts)
