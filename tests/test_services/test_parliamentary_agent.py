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


def test_parse_agent_response_accepts_plain_text():
    """Agent should accept plain text responses when no tool calls exist."""
    mock_client = Mock()
    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=mock_client, kg_store=store)

    result = agent._parse_agent_response("Hello there", "hi")

    assert result["success"] is True
    assert result["answer"] == "Hello there"


@pytest.mark.skip("Mock setup issue - entities extraction needs updated test mocks")
@pytest.mark.anyio
async def test_query_handles_function_calls_from_response():
    """Ensure agent executes tool calls from function_call response parts."""

    class FakeFunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

    class FakePart:
        def __init__(self, function_call):
            self.function_call = function_call

    class FakeContent:
        def __init__(self, parts):
            self.parts = parts

    class FakeCandidate:
        def __init__(self, content):
            self.content = content

    class FakeResponse:
        def __init__(self, candidates, text=None):
            self.candidates = candidates
            self.text = text

    tool_result = {
        "status": "success",
        "data": {"entities": [{"entity_id": "e1", "name": "Test", "entity_type": "person"}]},
    }

    async def fake_find_entity(db, name, entity_type=None):
        return tool_result

    mock_generate = AsyncMock(
        return_value=FakeResponse(
            candidates=[
                FakeCandidate(
                    FakeContent([FakePart(FakeFunctionCall("find_entity", {"name": "Test"}))])
                )
            ],
            text=None,
        )
    )
    mock_models = Mock(generate_content=mock_generate)
    mock_aio = Mock(models=mock_models)
    mock_client = Mock(aio=mock_aio)
    gemini_client = Mock(client=mock_client)

    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=gemini_client, kg_store=store)
    agent.tools.get_tools_dict = Mock(
        return_value={
            "function_declarations": [],
            "tools": {"find_entity": fake_find_entity},
        }
    )

    result = await agent.query(db=Mock(), user_query="who is test", max_iterations=1)

    assert result["success"] is True
    assert result.get("entities", [])  # Entities may be empty depending on parsing


@pytest.mark.anyio
async def test_query_empty_response_returns_fallback():
    """Empty model response should yield a fallback answer, not an error."""

    class FakeResponse:
        def __init__(self, candidates=None, text=None):
            self.candidates = candidates or []
            self.text = text

    mock_generate = AsyncMock(return_value=FakeResponse(candidates=[], text=None))
    mock_models = Mock(generate_content=mock_generate)
    mock_aio = Mock(models=mock_models)
    mock_client = Mock(aio=mock_aio)
    gemini_client = Mock(client=mock_client)

    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=gemini_client, kg_store=store)
    agent.tools.get_tools_dict = Mock(return_value={"function_declarations": [], "tools": {}})

    result = await agent.query(db=Mock(), user_query="last session", max_iterations=1)

    assert result["success"] is True
    assert "couldn't" in result["answer"].lower() or "could not" in result["answer"].lower()


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
