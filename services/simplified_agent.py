"""Simplified parliamentary agent using single hybrid GraphRAG approach."""

from typing import Any

from google.genai import types
from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.message import Message
from models.session import Session
from services.gemini import GeminiClient
from services.response_styler import ResponseStyler
from services.hybrid_graphrag import HybridGraphRAG, HybridSearchResult, GraphContext


class SimplifiedAgent:
    """
    Simplified parliamentary agent using single hybrid GraphRAG approach.

    Eliminates:
    - Complex function-calling loops
    - Multiple LLM calls (planning + synthesis)
    - Dual-path fallback logic

    Uses:
    - Single hybrid GraphRAG search
    - One LLM synthesis call
    - Rich graph context
    """

    def __init__(
        self,
        gemini_client: GeminiClient,
        hybrid_rag: HybridGraphRAG,
    ):
        """Initialize simplified agent.

        Args:
            gemini_client: Gemini client for LLM calls
            hybrid_rag: Unified hybrid GraphRAG service
        """
        self.client = gemini_client
        self.hybrid_rag = hybrid_rag
        self.response_styler = ResponseStyler()
        self.max_history_messages = 6
        self.max_output_tokens = 1024

    async def query(
        self,
        db: AsyncSession,
        user_query: str,
        session_id: str | None = None,
    ) -> dict:
        """
        Process query using single hybrid GraphRAG approach.

        Flow:
        1. Execute hybrid GraphRAG search (vector + graph expansion)
        2. Build synthesis prompt with rich graph context
        3. Generate response with ONE LLM call

        Args:
            db: Database session
            user_query: User's natural language question
            session_id: Optional session ID for conversation context

        Returns:
            Structured response with answer, entities, and follow-up suggestions
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"🔍 Simplified agent query: '{user_query}'")

        search_result = await self.hybrid_rag.search(
            db=db,
            query=user_query,
            max_context_segments=15,
        )

        if not search_result.success:
            return {
                "success": True,
                "answer": "I couldn't find enough information to answer that question. Try asking about a specific speaker, bill, or topic.",
                "entities": [],
                "follow_up_suggestions": [
                    "Try rephrasing your question",
                    "Search for a specific topic",
                    "Browse recent sessions",
                ],
            }

        synthesis = await self._synthesize_with_llm(
            graph_context=search_result.context,
            user_query=user_query,
            db=db,
            session_id=session_id,
        )

        return {
            "success": True,
            "answer": synthesis["answer"],
            "entities": search_result.entities_found,
            "follow_up_suggestions": synthesis["follow_up_suggestions"],
        }

    async def _synthesize_with_llm(
        self,
        graph_context: GraphContext,
        user_query: str,
        db: AsyncSession,
        session_id: str | None = None,
    ) -> dict:
        """
        Generate conversational response from graph context using ONE LLM call.

        Args:
            graph_context: Rich graph context from hybrid search
            user_query: Original user question
            db: Database session
            session_id: Optional session ID for conversation history

        Returns:
            Dict with answer and follow-up suggestions
        """
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"🔄 LLM synthesis. Context: {len(graph_context.segments)} segments, "
            f"{len(graph_context.seed_entities)} seed entities, "
            f"{len(graph_context.relationships)} relationships, Session ID: {session_id}"
        )

        try:
            history = []
            if session_id:
                result = await db.execute(select(Session).where(Session.session_id == session_id))
                session = result.scalar_one_or_none()

                if session:
                    from models.message import Message as DBMessage

                    messages_result = await db.execute(
                        select(DBMessage)
                        .where(cast(DBMessage.session_id, String) == str(session.id))
                        .order_by(DBMessage.created_at.desc())
                        .limit(self.max_history_messages)
                    )

                    messages = messages_result.scalars().all()

                    for msg in messages:
                        if msg.role == "user":
                            history.append(f"User: {msg.content}")
                        elif msg.structured_response:
                            details = msg.structured_response.get("response_cards", [{}])[0].get(
                                "details", ""
                            )
                            history.append(f"Assistant: {details[:150]}...")

            history_text = " | ".join(history[-2:]) if history else "No previous conversation."

            context_text = self._build_graph_context_for_llm(graph_context)

            synthesis_prompt = f"""You are YuhHearDem, a civic AI assistant helping Barbadians understand Parliament.

Recent context: {history_text}

User query: {user_query}

Graph context:
{context_text}

Write a clear, conversational response that:
- Starts with a warm Bajan greeting
- Summarizes what was said and why it matters
- Uses inline citations with YouTube links
- Mentions speakers, dates, and sessions
- Ends with a brief supportive outro

Use the compressed JSON graph context above to ground your answer. Use segments[].url for citations.
"""

            logger.debug("LLM synthesis prompt:\n%s", synthesis_prompt)

            response = await self.client.client.aio.models.generate_content(
                model=self.client.model,
                contents=[
                    types.Content(role="user", parts=[types.Part.from_text(text=synthesis_prompt)])
                ],
                config=types.GenerateContentConfig(
                    temperature=self.client.temperature,
                    max_output_tokens=self.max_output_tokens,
                ),
            )

            answer_text = ""
            candidates = response.candidates or []
            for candidate in candidates:
                if candidate.content:
                    parts = candidate.content.parts or []
                    for part in parts:
                        if part.text:
                            answer_text += part.text

            follow_ups = self._generate_follow_up_suggestions(graph_context, user_query)

            answer_text = self._append_sources_if_missing(
                answer_text
                or "I found some information but had trouble interpreting it. Could you try rephrasing?",
                graph_context,
            )
            answer_text = self._ensure_answer_with_fallback(
                answer_text,
                graph_context,
                user_query,
            )

            return {
                "answer": answer_text,
                "follow_up_suggestions": follow_ups,
            }

        except Exception as e:
            import logging

            logger.exception("LLM synthesis failed", exc_info=e)

            follow_ups = [
                "Try rephrasing your question",
                "Search for a specific topic",
                "Browse recent sessions",
            ]

            return {
                "answer": "Sorry, I ran into a small issue: I found some information but had trouble interpreting it properly.",
                "follow_up_suggestions": follow_ups,
            }

    def _build_graph_context_for_llm(self, context: GraphContext) -> str:
        """Build compressed JSON graph context for LLM synthesis."""
        import json

        def _compact_entity(entity: dict) -> dict:
            return {
                "id": entity.get("entity_id", ""),
                "name": entity.get("name", ""),
                "type": entity.get("type", ""),
            }

        def _compact_relationship(rel: dict) -> dict:
            return {
                "source": rel.get("source_id", ""),
                "target": rel.get("target_id", ""),
                "type": rel.get("relation_type", ""),
                "path": rel.get("path_names") or rel.get("path", ""),
                "confidence": rel.get("confidence"),
            }

        def _compact_segment(seg: dict) -> dict:
            text = " ".join(seg.get("text", "").split())
            snippet = text[:180]
            return {
                "video_title": seg.get("video_title", "Unknown"),
                "speaker": seg.get("speaker_id", ""),
                "text": snippet,
                "url": self._build_timestamped_url(seg) or "",
            }

        payload = {
            "seed_entities": [_compact_entity(e) for e in context.seed_entities[:5]],
            "related_entities": [_compact_entity(e) for e in context.related_entities[:5]],
            "relationships": [_compact_relationship(r) for r in context.relationships[:7]],
            "segments": [_compact_segment(s) for s in context.segments[:5]],
        }

        compressed = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)

        return f"Graph context (compressed JSON):\n{compressed}"

    def _build_timestamped_url(self, segment: dict) -> str | None:
        """Build a timestamped YouTube URL from a segment."""
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        youtube_url = segment.get("youtube_url")
        if not youtube_url:
            return None

        timestamp = segment.get("timestamp_seconds")
        if timestamp is None:
            return youtube_url

        parsed = urlparse(youtube_url)
        query = parse_qs(parsed.query)
        query["t"] = [f"{int(timestamp)}s"]
        new_query = urlencode(query, doseq=True)

        return urlunparse(parsed._replace(query=new_query))

    def _append_sources_if_missing(self, answer_text: str, context: GraphContext) -> str:
        """Append sources if the answer lacks citations."""
        cleaned_answer = self._strip_unlinked_sources_block(answer_text)

        if "youtube.com" in cleaned_answer or "youtu.be" in cleaned_answer:
            return cleaned_answer

        sources = []
        seen_urls = set()
        for seg in context.segments[:5]:
            url = self._build_timestamped_url(seg)
            title = seg.get("video_title", "Source")
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                sources.append(f"- [{title}]({url})")

        if not sources:
            return cleaned_answer

        return f"{cleaned_answer}\n\nSources:\n" + "\n".join(sources)

    def _ensure_answer_with_fallback(
        self,
        answer_text: str,
        context: GraphContext,
        user_query: str,
    ) -> str:
        """Ensure the response contains a substantive answer."""
        import re

        cleaned = self._strip_unlinked_sources_block(answer_text or "").strip()

        if not context.segments:
            return cleaned or answer_text

        sentences = [s for s in re.split(r"[.!?]", cleaned) if s.strip()]
        has_link = "http" in cleaned or "youtu" in cleaned
        is_too_short = len(cleaned) < 160 or len(sentences) < 2

        if not cleaned or is_too_short or not has_link:
            topic = user_query.rstrip("?").strip() or "this topic"
            lines = [f"Wuhloss, here is a straight summary on {topic}:"]

            for seg in context.segments[:3]:
                speaker = seg.get("speaker_id", "Speaker")
                video = seg.get("video_title", "Session")
                url = self._build_timestamped_url(seg)
                text = " ".join(seg.get("text", "").split())
                snippet = text[:180] if text else ""
                citation = f" ({url})" if url else ""
                if snippet:
                    lines.append(f'- {speaker} in {video}: "{snippet}"{citation}')

            return "\n".join(lines).strip()

        return cleaned

    def _strip_unlinked_sources_block(self, answer_text: str) -> str:
        """Remove a Sources block that lacks any links."""
        lines = answer_text.splitlines()

        for idx, line in enumerate(lines):
            if line.strip().lower().startswith("sources:"):
                end = idx + 1
                while end < len(lines) and lines[end].strip() != "":
                    end += 1

                block = lines[idx:end]
                if any("http" in block_line or "youtu" in block_line for block_line in block):
                    return answer_text

                cleaned_lines = lines[:idx] + lines[end:]
                while cleaned_lines and cleaned_lines[0].strip() == "":
                    cleaned_lines.pop(0)

                return "\n".join(cleaned_lines).rstrip()

        return answer_text

    def _generate_follow_up_suggestions(
        self,
        graph_context: GraphContext,
        user_query: str,
    ) -> list[str]:
        """Generate contextual follow-up suggestions from graph context."""
        import logging

        logger = logging.getLogger(__name__)
        suggestions = set()

        for entity in graph_context.seed_entities:
            name = entity.get("name", "")
            if name:
                suggestions.add(f"What else was said about {name}?")
                suggestions.add(f"Tell me more about {name}'s position on this.")

        if graph_context.related_entities:
            for entity in graph_context.related_entities[:3]:
                name = entity.get("name", "")
                if name:
                    suggestions.add(f"What relationships does {name} have with other entities?")

        if graph_context.segments:
            topics_mentioned = set()
            for seg in graph_context.segments[:3]:
                text = seg.get("text", "").lower()
                if "legislation" in text or "bill" in text:
                    topics_mentioned.add("What legislation is related to this discussion?")
                if "vote" in text or "division" in text:
                    topics_mentioned.add("What was the voting outcome?")
                if "oppose" in text or "concern" in text:
                    topics_mentioned.add("What concerns were raised?")

            for topic in topics_mentioned:
                suggestions.add(topic)

        if not suggestions:
            suggestions.update(
                [
                    "What legislation is related to this discussion?",
                    "How does this affect ordinary Barbadians?",
                    "What concerns were raised about this topic?",
                    "Which other ministers spoke about this?",
                    "What was the final outcome of this debate?",
                ]
            )

        result = list(suggestions)[:5]
        logger.info(f"   Generated {len(result)} follow-up suggestions")

        return result
