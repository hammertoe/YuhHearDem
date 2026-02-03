"""Tests for parliamentary agent"""

from unittest.mock import AsyncMock, Mock

import pytest

from services.parliamentary_agent import ParliamentaryAgent
from storage.knowledge_graph_store import KnowledgeGraphStore


def test_build_agent_prompt_includes_iteration_info():
    """Ensure prompt includes iteration and doesn't error on first iteration"""
    mock_client = Mock()
    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=mock_client, kg_store=store)

    prompt = agent._build_agent_prompt("What happened?", [], 1, 10)

    assert "Current iteration: 1/10" in prompt


@pytest.mark.anyio
async def test_query_uses_async_gemini_client():
    """Ensure agent uses async Gemini client for generate_content."""
    mock_generate = AsyncMock(return_value=Mock(text="function_calls"))
    mock_models = Mock(generate_content=mock_generate)
    mock_aio = Mock(models=mock_models)
    mock_client = Mock(aio=mock_aio)
    gemini_client = Mock(client=mock_client)

    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=gemini_client, kg_store=store)
    agent.tools.get_tools_dict = Mock(return_value={"function_declarations": []})
    agent._parse_agent_response = Mock(
        return_value={
            "success": True,
            "answer": "ok",
            "context": [],
            "iteration": 1,
            "tool_results": [],
        }
    )

    result = await agent.query(db=Mock(), user_query="hello", max_iterations=1)

    assert result["success"] is True
    mock_generate.assert_awaited_once()
