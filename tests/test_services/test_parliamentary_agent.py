"""Tests for parliamentary agent"""

from unittest.mock import Mock

from services.parliamentary_agent import ParliamentaryAgent
from storage.knowledge_graph_store import KnowledgeGraphStore


def test_build_agent_prompt_includes_iteration_info():
    """Ensure prompt includes iteration and doesn't error on first iteration"""
    mock_client = Mock()
    store = KnowledgeGraphStore()
    agent = ParliamentaryAgent(gemini_client=mock_client, kg_store=store)

    prompt = agent._build_agent_prompt("What happened?", [], 1, 10)

    assert "Current iteration: 1/10" in prompt
