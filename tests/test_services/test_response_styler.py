"""Tests for ResponseStyler service"""

from datetime import datetime

import pytest

from services.response_styler import ResponseStyler


class TestResponseStyler:
    """Test suite for ResponseStyler."""

    def setup_method(self):
        """Set up test instance."""
        self.styler = ResponseStyler()

    def test_generate_answer_from_latest_session(self):
        """Test generating answer from latest session results."""
        tool_results = [
            {
                "tool": "get_latest_session",
                "data": {
                    "title": "House of Assembly Sitting",
                    "session_date": "2024-03-15",
                    "session_type": "House of Assembly",
                    "topics": ["Budget 2024", "Healthcare Reform"],
                    "quotes": [
                        "We are committed to healthcare for all Barbadians.",
                        "The budget addresses key concerns.",
                    ],
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="What happened in the latest session?",
            is_success=True,
        )

        assert result is not None
        assert any(intro in result for intro in self.styler.BAJAN_INTROS)
        assert "House of Assembly Sitting" in result
        assert "Friday 15 March 2024" in result
        assert "Budget 2024" in result
        assert "Healthcare Reform" in result
        assert "We are committed to healthcare for all Barbadians." in result

    def test_generate_answer_from_semantic_search(self):
        """Test generating answer from semantic search results."""
        tool_results = [
            {
                "tool": "search_semantic",
                "data": {
                    "results": [
                        {
                            "text": "The sugar tax is important for public health.",
                            "video_title": "Senate Debate",
                            "timestamp_seconds": 120,
                            "speaker": "Senator Cummins",
                        },
                        {
                            "text": "We must balance health concerns with economic impact.",
                            "video_title": "House of Assembly",
                            "timestamp_seconds": 300,
                            "speaker": "Minister of Health",
                        },
                    ]
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="What was said about sugar tax?",
            is_success=True,
        )

        assert "Found 2 relevant segment(s)" in result
        assert "The sugar tax is important for public health." in result
        assert "Senator Cummins" in result
        assert "120s" in result or "120" in result
        assert "We must balance health concerns with economic impact." in result

    def test_generate_answer_with_mentions(self):
        """Test generating answer from entity mentions."""
        tool_results = [
            {
                "tool": "get_mentions",
                "data": {
                    "mentions": [
                        {
                            "text": "The NCD burden is significant in Barbados.",
                            "speaker": "Dr. Sonia Browne",
                            "video_title": "Health Committee Meeting",
                            "timestamp": "45:00",
                            "context": "NCD burden",
                        },
                        {
                            "text": "We need comprehensive NCD prevention strategies.",
                            "speaker": "Minister of Health",
                            "video_title": "Senate Health Debate",
                            "timestamp": "120:30",
                            "context": "NCD prevention",
                        },
                    ]
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="What was said about NCDs?",
            is_success=True,
        )

        assert "Found 2 mention(s)" in result
        assert "Dr. Sonia Browne" in result
        assert "The NCD burden is significant in Barbados." in result
        assert "Minister of Health" in result
        assert "We need comprehensive NCD prevention strategies." in result

    def test_generate_no_results_response(self):
        """Test response when no results found."""
        result = self.styler.style_response(
            tool_results=[],
            user_query="What about unicorns?",
            is_success=True,
        )

        assert result is not None
        assert any(text in result for text in self.styler.BAJAN_INTROS)
        assert any(text in result for text in self.styler.BAJAN_OUTROS)

    def test_generate_error_response(self):
        """Test error response styling."""
        error_msg = "Database connection failed"
        result = self.styler.style_response(
            tool_results=[],
            user_query="Test question",
            is_success=False,
            error_message=error_msg,
        )

        assert result is not None
        assert "Database connection failed" in result

    def test_follow_up_suggestions_from_latest_session(self):
        """Test generating follow-up suggestions from latest session."""
        tool_results = [
            {
                "tool": "get_latest_session",
                "data": {
                    "title": "House Sitting",
                    "session_type": "House of Assembly",
                    "topics": ["Budget", "Healthcare", "Education"],
                },
            }
        ]

        suggestions = self.styler.generate_follow_up_suggestions(
            tool_results=tool_results,
            user_query="What happened in the latest session?",
        )

        assert len(suggestions) > 0
        assert len(suggestions) <= 5
        assert any("Budget" in s for s in suggestions)
        assert any("Healthcare" in s for s in suggestions)

    def test_follow_up_suggestions_from_mentions(self):
        """Test generating follow-up suggestions from mentions."""
        tool_results = [
            {
                "tool": "get_mentions",
                "data": {
                    "mentions": [
                        {
                            "text": "The sugar tax is important.",
                            "speaker": "Senator Cummins",
                            "context": "sugar tax burden",
                        },
                        {
                            "text": "Health outcomes depend on diet.",
                            "speaker": "Minister of Health",
                            "context": "public health impact",
                        },
                    ]
                },
            }
        ]

        suggestions = self.styler.generate_follow_up_suggestions(
            tool_results=tool_results,
            user_query="What was said about sugar tax?",
        )

        assert len(suggestions) > 0
        assert len(suggestions) <= 5

    def test_follow_up_suggestions_default(self):
        """Test default follow-up suggestions when no results."""
        suggestions = self.styler.generate_follow_up_suggestions(
            tool_results=[],
            user_query="Random question",
        )

        assert len(suggestions) > 0
        assert len(suggestions) <= 5

    def test_format_date(self):
        """Test date formatting."""
        date_str = "2024-03-15T10:30:00Z"
        formatted = self.styler._format_date(date_str)

        assert formatted == "Friday 15 March 2024"

    def test_format_date_iso(self):
        """Test date formatting with ISO format - fromisoformat can parse YYYY-MM-DD."""
        date_str = "2024-03-15"
        formatted = self.styler._format_date(date_str)

        assert formatted == "Friday 15 March 2024"

    def test_format_entity(self):
        """Test entity formatting."""
        tool_results = [
            {
                "tool": "find_entity",
                "data": {
                    "entities": [
                        {
                            "name": "Dr. Sonia Browne",
                            "entity_type": "Person",
                            "description": "Minister of Health",
                        }
                    ]
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="Who is Dr. Sonia Browne?",
            is_success=True,
        )

        assert "Dr. Sonia Browne" in result
        assert "Person" in result
        assert "Minister of Health" in result

    def test_format_relationships(self):
        """Test relationship formatting."""
        tool_results = [
            {
                "tool": "get_relationships",
                "data": {
                    "relationships": [
                        {
                            "source_id": "Budget",
                            "target_id": "Healthcare",
                            "relation_type": "funds",
                            "evidence": "The budget allocates $50M to healthcare initiatives.",
                        }
                    ]
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="What is the relationship between budget and healthcare?",
            is_success=True,
        )

        assert "Budget" in result
        assert "Healthcare" in result
        assert "funds" in result
        assert "budget allocates" in result.lower()

    def test_response_has_intro_and_outro(self):
        """Test that responses always have intro and outro."""
        tool_results = [
            {
                "tool": "search_semantic",
                "data": {
                    "results": [
                        {
                            "text": "Test content",
                            "video_title": "Test Video",
                        }
                    ]
                },
            }
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="Test question",
            is_success=True,
        )

        has_intro = any(intro in result for intro in self.styler.BAJAN_INTROS)
        has_outro = any(outro in result for outro in self.styler.BAJAN_OUTROS)

        assert has_intro
        assert has_outro

    def test_multiple_tool_results(self):
        """Test handling multiple tool results."""
        tool_results = [
            {
                "tool": "find_entity",
                "data": {
                    "entities": [
                        {
                            "name": "Budget Bill",
                            "entity_type": "Legislation",
                            "description": "Annual budget legislation.",
                        }
                    ]
                },
            },
            {
                "tool": "get_mentions",
                "data": {
                    "mentions": [
                        {
                            "text": "The budget bill was passed today.",
                            "speaker": "Speaker of the House",
                            "video_title": "House Sitting",
                        }
                    ]
                },
            },
        ]

        result = self.styler.style_response(
            tool_results=tool_results,
            user_query="Tell me about the Budget Bill.",
            is_success=True,
        )

        assert "Budget Bill" in result
        assert "The budget bill was passed today." in result
        assert "Speaker of the House" in result
