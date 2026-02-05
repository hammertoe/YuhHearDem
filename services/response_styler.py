"""Response styling service for YuhHearDem chat system."""

import random
from typing import Any


class ResponseStyler:
    """Styles responses with Bajan personality and evidence-first formatting."""

    BAJAN_INTROS = [
        "Alright, I've been lookin' into what's been said... and I got some good info for ya!",
        "Alright, let me see what they were saying about that in Parliament...",
        "Get straight to what dey really say - here's the run-down...",
        "Listen nuh, I checked the records and this is what I found...",
        "Gih yuh this straight - I did the digging and here's what came up...",
        "Alright, I did me homework and this is the real deal...",
        "Let me break it down for yuh - here's what they said in the House...",
        "Gine tell yuh straight - I found the receipts in Parliament...",
        "Alright, check dis nuh - here's what was really said...",
        "Listen good now, this is what I dug up from the sittings...",
    ]

    BAJAN_OUTROS = [
        "\n\n---\n\nWant to know more? Ask me about any of the above, and I'll get yuh more details!",
        "\n\n---\n\nAnything else yuh want to know? I'm here to help yuh understand what's really going on!",
        "\n\n---\n\nThat's the gist of it, but there's always more to dig into. What else yuh curious about?",
        "\n\n---\n\nAnything else pique yuh interest? Just ask and I'll find out what they said!",
        "\n\n---\n\nYuh want to go deeper into any of this? Just let me know!",
        "\n\n---\n\nThat's what the records show. Anything else yuh want to know about this?",
    ]

    SUGGESTION_TEMPLATES = [
        "What else was said about {topic}?",
        "Tell me more about {entity}'s position on this.",
        "Did anyone oppose this?",
        "What legislation is related to this discussion?",
        "How does this affect ordinary Barbadians?",
        "What evidence was presented for this claim?",
        "What was the final outcome of this debate?",
        "Which other ministers spoke about this?",
        "Show me all mentions of {topic}.",
        "What was said in the Senate about this?",
        "What concerns were raised about {topic}?",
        "What are the next steps for this issue?",
    ]

    def __init__(self):
        """Initialize response styler."""
        pass

    def get_random_intro(self) -> str:
        """Get a random Bajan intro message."""
        return random.choice(self.BAJAN_INTROS)

    def get_random_outro(self) -> str:
        """Get a random Bajan outro message."""
        return random.choice(self.BAJAN_OUTROS)

    def style_response(
        self,
        tool_results: list[dict],
        user_query: str,
        is_success: bool = True,
        error_message: str | None = None,
    ) -> str:
        """
        Style a response with Bajan personality and evidence-first formatting.

        Args:
            tool_results: Results from agent tools
            user_query: Original user question
            is_success: Whether the query was successful
            error_message: Error message if not successful

        Returns:
            Styled response text
        """
        if not is_success and error_message:
            return self._style_error_response(error_message)

        intro = self.get_random_intro()
        body = self._generate_evidence_first_body(tool_results, user_query)
        outro = self.get_random_outro()

        return f"{intro}\n\n{body}{outro}"

    def _generate_evidence_first_body(self, tool_results: list[dict], user_query: str) -> str:
        """
        Generate evidence-first body content.

        Structure:
        - Direct quotations with attribution
        - Chronological synthesis of multi-source info
        - Clear speaker and date attribution
        """
        if not tool_results:
            return self._style_no_results_response()

        parts = []

        for tool_result in tool_results:
            tool = tool_result.get("tool")
            data = tool_result.get("data", {})

            if tool == "get_latest_session":
                parts.extend(self._format_latest_session(data))
            elif tool in ("search_by_date_range", "search_by_speaker"):
                parts.extend(self._format_search_results(data))
            elif tool == "search_semantic":
                parts.extend(self._format_semantic_results(data))
            elif tool == "get_mentions":
                parts.extend(self._format_mentions(data))
            elif tool == "find_entity":
                parts.extend(self._format_entity(data))
            elif tool == "get_relationships":
                parts.extend(self._format_relationships(data))

        if not parts:
            return self._style_no_results_response()

        return "\n\n".join(parts)

    def _format_latest_session(self, data: dict) -> list[str]:
        """Format latest session results with quotes."""
        parts = []

        title = data.get("title", "Recent session")
        date = data.get("session_date", "")
        topics = data.get("topics", [])
        quotes = data.get("quotes", [])
        session_type = data.get("session_type", "")
        video_id = data.get("video_id", "")
        video_url = data.get("youtube_url", "") or data.get("video_url", "")

        if date:
            date_str = self._format_date(date)
            session_info = f"**{title}** ({date_str})"
            if session_type:
                session_info += f" - {session_type}"
            parts.append(session_info)

            if video_id and not video_url:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
            if video_url:
                parts.append(f"📺 **Watch the full session:** [{title}]({video_url})")

        if topics:
            parts.append("\n**What was discussed:**")
            for i, topic in enumerate(topics[:5], 1):
                parts.append(f"{i}. {topic}")

        if quotes:
            parts.append("\n**What they said:**")
            for i, quote in enumerate(quotes[:3], 1):
                parts.append(f'\n> "{quote}"')

        return parts

    def _format_search_results(self, data: dict) -> list[str]:
        """Format session search results."""
        parts = []
        sessions = data.get("sessions", [])

        if not sessions:
            return parts

        parts.append(f"**Found {len(sessions)} session(s):**")

        for session in sessions:
            title = session.get("title", "Unknown session")
            date = session.get("session_date", "")
            transcript = session.get("transcript", {})

            if date:
                date_str = self._format_date(date)
                parts.append(f"\n**{title}** ({date_str})")

            agenda_items = transcript.get("agenda_items", [])
            if agenda_items:
                parts.append("\nKey topics:")
                for item in agenda_items[:3]:
                    topic = item.get("topic_title", "")
                    if topic:
                        parts.append(f"• {topic}")

                speech_blocks = []
                for item in agenda_items[:2]:
                    blocks = item.get("speech_blocks", [])
                    for block in blocks[:2]:
                        sentences = block.get("sentences", [])
                        for sentence in sentences[:1]:
                            text = sentence.get("text", "")
                            speaker = sentence.get("speaker", "")
                            if text:
                                if speaker:
                                    speech_blocks.append(f'**{speaker}**: "{text}"')
                                else:
                                    speech_blocks.append(f'"{text}"')

                if speech_blocks:
                    parts.append("\n**Direct quotes:**")
                    for quote in speech_blocks[:2]:
                        parts.append(f"\n> {quote}")

        return parts

    def _format_semantic_results(self, data: dict) -> list[str]:
        """Format semantic search results with quotes."""
        parts = []
        results = data.get("results", [])

        if not results:
            return parts

        parts.append(f"**Found {len(results)} relevant segment(s):**")

        for result in results[:3]:
            text = result.get("text", "")
            video_title = result.get("video_title", "")
            video_date = result.get("session_date", "")
            youtube_id = result.get("youtube_id", "")
            timestamp = result.get("timestamp_seconds")
            speaker = result.get("speaker", "")

            if not text:
                continue

            if video_title:
                date_str = f" ({self._format_date(video_date)})" if video_date else ""
                parts.append(f"\n**From {video_title}{date_str}:**")

            if youtube_id:
                youtube_url = self._create_youtube_link(youtube_id, timestamp)
                link_label = (
                    f"{video_title or 'Session'} @ {int(timestamp)}s"
                    if timestamp
                    else (video_title or "Session")
                )
                parts.append(f"📺 **Watch this moment:** [{link_label}]({youtube_url})")

            if timestamp and not youtube_id:
                parts.append(f"*At {timestamp}s into the session*")

            if speaker:
                parts.append(f"**{speaker} said:**")

            parts.append(f'\n> "{text}"')

        return parts

    def _format_mentions(self, data: dict) -> list[str]:
        """Format entity mention results."""
        parts = []
        mentions = data.get("mentions", [])

        if not mentions:
            return parts

        parts.append(f"**Found {len(mentions)} mention(s):**")

        for mention in mentions[:5]:
            text = mention.get("text", "")
            speaker = mention.get("speaker", "")
            video_title = mention.get("video_title", "")
            youtube_id = mention.get("youtube_id", "")
            timestamp = mention.get("timestamp")

            if not text:
                continue

            if video_title:
                parts.append(f"\n**{video_title}**")

            if youtube_id:
                youtube_url = self._create_youtube_link(youtube_id, timestamp)
                link_label = (
                    f"{video_title or 'Session'} @ {timestamp}"
                    if timestamp
                    else (video_title or "Session")
                )
                parts.append(f"📺 **Watch this moment:** [{link_label}]({youtube_url})")

            if timestamp and not youtube_id:
                parts.append(f"*{timestamp}*")

            if speaker:
                parts.append(f"**{speaker} said:**")

            parts.append(f'\n> "{text}"')

        return parts

        parts.append(f"**Found {len(mentions)} mention(s):**")

        for mention in mentions[:5]:
            text = mention.get("text", "")
            speaker = mention.get("speaker", "")
            video_title = mention.get("video_title", "")
            timestamp = mention.get("timestamp")

            if not text:
                continue

            if video_title:
                parts.append(f"\n**{video_title}**")
                if timestamp:
                    parts.append(f"*{timestamp}s*")

            if speaker:
                parts.append(f"**{speaker} said:**")

            parts.append(f'\n> "{text}"')

        return parts

    def _format_entity(self, data: dict) -> list[str]:
        """Format entity search results."""
        parts = []
        entities = data.get("entities", [])

        if not entities:
            return parts

        entity = entities[0]
        name = entity.get("name", "")
        entity_type = entity.get("entity_type", "")
        description = entity.get("description", "")

        if name:
            parts.append(f"**{name}**")
            if entity_type:
                parts.append(f"*Type: {entity_type}*")

        if description:
            parts.append(f"\n{description}")

        return parts

    def _format_relationships(self, data: dict) -> list[str]:
        """Format relationship results."""
        parts = []
        relationships = data.get("relationships", [])

        if not relationships:
            return parts

        parts.append(f"**Found {len(relationships)} relationship(s):**")

        for rel in relationships[:3]:
            source = rel.get("source_id", "")
            target = rel.get("target_id", "")
            rel_type = rel.get("relation_type", "")
            evidence = rel.get("evidence", "")

            if source and target:
                parts.append(f"\n• **{source}** → **{target}**")
                if rel_type:
                    parts.append(f"  *{rel_type}*")
                if evidence:
                    parts.append(f'  "{evidence[:200]}..."')

        return parts

    def _format_date(self, date_str: str) -> str:
        """Format a date string to readable format."""
        if not date_str:
            return ""

        try:
            from datetime import datetime

            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return date_obj.strftime("%A %d %B %Y")
        except Exception:
            return date_str

    def _create_youtube_link(self, video_id: str, timestamp: int | float | None = None) -> str:
        """Create a clickable YouTube link with optional timestamp."""
        if not video_id:
            return ""

        base_url = f"https://www.youtube.com/watch?v={video_id}"

        if timestamp is not None:
            try:
                seconds = int(float(timestamp))
                base_url += f"&t={seconds}s"
            except (ValueError, TypeError):
                pass

        return base_url

    def _style_no_results_response(self) -> str:
        """Style response when no results found."""
        intros = [
            "Listen, I searched through the records but couldn't find anything specific about that.",
            "I looked through the parliamentary proceedings, but I'm not seeing any direct mentions of that.",
            "Sorry nuh, I checked the records but came up empty on that one.",
            "I did some digging, but the records don't seem to have anything on that particular topic yet.",
        ]
        return random.choice(intros)

    def _style_error_response(self, error_message: str) -> str:
        """Style error response with Bajan personality."""
        intros = [
            f"Wah gine on here - I ran into a small issue: {error_message}",
            f"Sorry, I hit a bump in the road: {error_message}",
            f"Listen, something went wrong: {error_message}",
        ]
        return random.choice(intros)

    def generate_follow_up_suggestions(
        self,
        tool_results: list[dict],
        user_query: str,
    ) -> list[str]:
        """
        Generate contextual follow-up suggestions based on results.

        Args:
            tool_results: Results from agent tools
            user_query: Original user question

        Returns:
            List of follow-up suggestions
        """
        suggestions = set()

        for tool_result in tool_results:
            tool = tool_result.get("tool")
            data = tool_result.get("data", {})

            if tool == "get_latest_session":
                suggestions.update(self._suggest_from_latest_session(data))
            elif tool in ("search_by_date_range", "search_by_speaker", "search_semantic"):
                suggestions.update(self._suggest_from_search_results(data))
            elif tool == "get_mentions":
                suggestions.update(self._suggest_from_mentions(data))
            elif tool == "find_entity":
                suggestions.update(self._suggest_from_entity(data))

        if not suggestions:
            suggestions.update(self._default_suggestions())

        return list(suggestions)[:5]

    def _suggest_from_latest_session(self, data: dict) -> set[str]:
        """Generate suggestions from latest session."""
        suggestions = set()

        topics = data.get("topics", [])
        for topic in topics[:2]:
            suggestions.add(f"What else was said about {topic}?")

        session_type = data.get("session_type", "")
        if session_type.lower() == "house of assembly":
            suggestions.add("What was said in the Senate about this?")

        suggestions.add("Tell me more about the key speakers in this session.")
        suggestions.add("What legislation was discussed?")

        return suggestions

    def _suggest_from_search_results(self, data: dict) -> set[str]:
        """Generate suggestions from search results."""
        suggestions = set()

        sessions = data.get("sessions", [])
        for session in sessions[:2]:
            transcript = session.get("transcript", {})
            agenda_items = transcript.get("agenda_items", [])

            for item in agenda_items[:1]:
                topic = item.get("topic_title", "")
                if topic:
                    suggestions.add(f"What concerns were raised about {topic}?")

        speakers_found = set()
        for session in sessions[:2]:
            transcript = session.get("transcript", {})
            agenda_items = transcript.get("agenda_items", [])

            for item in agenda_items[:2]:
                blocks = item.get("speech_blocks", [])
                for block in blocks[:1]:
                    sentences = block.get("sentences", [])
                    for sentence in sentences[:1]:
                        speaker = sentence.get("speaker", "")
                        if speaker and speaker not in speakers_found:
                            speakers_found.add(speaker)
                            suggestions.add(f"Tell me more about {speaker}'s position on this.")

        return suggestions

    def _suggest_from_mentions(self, data: dict) -> set[str]:
        """Generate suggestions from mentions."""
        suggestions = set()

        mentions = data.get("mentions", [])

        topics_found = set()
        for mention in mentions[:3]:
            context = mention.get("context", "")
            speaker = mention.get("speaker", "")
            video_title = mention.get("video_title", "")

            if context and len(context.split()) > 2:
                words = context.split()[:3]
                potential_topic = " ".join(words)
                topics_found.add(potential_topic)

            if speaker:
                suggestions.add(f"What else has {speaker} said about this?")

        for topic in list(topics_found)[:2]:
            suggestions.add(f"Show me all mentions of {topic}...")

        return suggestions

    def _suggest_from_entity(self, data: dict) -> set[str]:
        """Generate suggestions from entity results."""
        suggestions = set()

        entities = data.get("entities", [])
        for entity in entities[:2]:
            name = entity.get("name", "")
            if name:
                suggestions.add(f"What relationships does {name} have with other entities?")
                suggestions.add(f"Show me all mentions of {name}.")

        return suggestions

    def _default_suggestions(self) -> set[str]:
        """Default fallback suggestions."""
        return {
            "What legislation is related to this discussion?",
            "How does this affect ordinary Barbadians?",
            "What evidence was presented for these claims?",
            "Which other ministers spoke about this?",
            "What concerns were raised about this topic?",
        }
