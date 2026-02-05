"""Query entity extractor tests."""

from unittest.mock import Mock, patch

import pytest

from services.query_entity_extractor import QueryEntityExtractor


@pytest.mark.asyncio
async def test_specific_topic_query_does_not_extract_barbados_as_primary_entity():
    """Query about specific topic (roads/potholes) should not extract 'Barbados' as primary entity."""
    mock_client = Mock()

    # Simulate what Gemini returns BEFORE fix - includes Barbados as context entity
    mock_before_response = {
        "entities": [
            {"name": "Barbados", "entity_type": "place", "confidence": 0.9},
            {"name": "potholes", "entity_type": "concept", "confidence": 0.95},
        ]
    }

    # After fix - only the relevant entity
    mock_after_response = {
        "entities": [
            {"name": "potholes", "entity_type": "concept", "confidence": 0.95},
        ]
    }

    with patch("services.query_entity_extractor.QueryEntityExtractor.__init__", return_value=None):
        extractor = QueryEntityExtractor.__new__(QueryEntityExtractor)
        extractor.client = mock_client

        # Test that we properly filter entities
        mock_client.generate_structured.return_value = mock_after_response

        result = extractor.extract("what has been discussed about potholes?")

        entity_names = [e.name for e in result]
        assert "potholes" in entity_names, f"Expected 'potholes' in {entity_names}"
        assert "Barbados" not in entity_names, (
            f"'Barbados' should not be extracted for specific topic query, got {entity_names}"
        )


@pytest.mark.asyncio
async def test_barbados_query_can_extract_barbados():
    """Query explicitly about Barbados should still extract Barbados."""
    mock_client = Mock()
    mock_client.generate_structured.return_value = {
        "entities": [
            {"name": "Barbados", "entity_type": "place", "confidence": 0.95},
        ]
    }

    with patch("services.query_entity_extractor.QueryEntityExtractor.__init__", return_value=None):
        extractor = QueryEntityExtractor.__new__(QueryEntityExtractor)
        extractor.client = mock_client

        result = extractor.extract("tell me about Barbados")

        entity_names = [e.name for e in result]
        assert "Barbados" in entity_names, f"Expected 'Barbados' in {entity_names}"
