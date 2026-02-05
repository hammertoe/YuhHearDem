"""Tests for SimplifiedAgent behavior."""

from unittest.mock import Mock

from services.hybrid_graphrag import GraphContext
from services.simplified_agent import SimplifiedAgent


def test_build_graph_context_includes_timestamped_links():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        segments=[
            {
                "text": "Road repairs were discussed.",
                "video_title": "House Sitting",
                "youtube_url": "https://youtube.com/watch?v=abc123",
                "timestamp_seconds": 123,
                "speaker_id": "Speaker",
            }
        ]
    )

    rendered = agent._build_graph_context_for_llm(context)

    assert "https://youtube.com" in rendered
    assert "t=123s" in rendered


def test_append_sources_when_answer_has_no_links():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        segments=[
            {
                "video_title": "Budget Debate",
                "youtube_url": "https://youtube.com/watch?v=xyz789",
                "timestamp_seconds": 45,
            }
        ]
    )

    updated = agent._append_sources_if_missing("Answer without links.", context)

    assert "Sources:" in updated
    assert "https://youtube.com" in updated


def test_append_sources_skips_when_links_present():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        segments=[
            {
                "video_title": "Budget Debate",
                "youtube_url": "https://youtube.com/watch?v=xyz789",
                "timestamp_seconds": 45,
            }
        ]
    )

    answer = "See [Budget Debate](https://youtube.com/watch?v=xyz789&t=45s)."
    updated = agent._append_sources_if_missing(answer, context)

    assert updated == answer


def test_append_sources_replaces_unlinked_sources_block():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        segments=[
            {
                "video_title": "House Sitting",
                "youtube_url": "https://youtu.be/abc123",
                "timestamp_seconds": 30,
            }
        ]
    )

    answer = "Summary text.\n\nSources:\nTHE HONOURABLE THE HOUSE OF ASSEMBLY"
    updated = agent._append_sources_if_missing(answer, context)

    assert "Sources:" in updated
    assert "[House Sitting](https://youtu.be/abc123?t=30s)" in updated
    assert "\nTHE HONOURABLE THE HOUSE OF ASSEMBLY" not in updated


def test_build_graph_context_compacts_relationships():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        seed_entities=[
            {"name": "Barbados", "type": "place", "importance": 0.8},
        ],
        related_entities=[
            {"name": "Road Traffic Act", "type": "law", "importance": 0.9},
        ],
        relationships=[
            {"path_names": "Barbados -> Road Traffic Act", "hop_count": 1} for _ in range(12)
        ],
        segments=[],
    )

    rendered = agent._build_graph_context_for_llm(context)

    assert '"relationships"' in rendered
    assert '"seed_entities"' in rendered
    assert '"related_entities"' in rendered
    assert '"segments"' in rendered


def test_ensure_answer_with_fallback_when_too_short():
    agent = SimplifiedAgent(gemini_client=Mock(), hybrid_rag=Mock())

    context = GraphContext(
        segments=[
            {
                "text": "We will increase the number of pothole patching teams and adjust scheduling.",
                "video_title": "House Sitting",
                "youtube_url": "https://youtu.be/abc123",
                "timestamp_seconds": 45,
                "speaker_id": "S. J. O. Bradshaw",
            }
        ]
    )

    answer = "Wuhloss, greetings!"
    updated = agent._ensure_answer_with_fallback(answer, context, "potholes")

    assert "pothole" in updated.lower()
    assert "https://youtu.be/abc123?t=45s" in updated
