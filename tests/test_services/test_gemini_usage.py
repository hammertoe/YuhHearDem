"""Tests for Gemini usage accounting."""

from types import SimpleNamespace

from services import gemini as gemini_module


class DummyClient:
    """Stub Gemini API client."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key


def test_gemini_records_usage(monkeypatch):
    """Gemini client should record usage metadata."""
    monkeypatch.setattr(gemini_module.genai, "Client", DummyClient)

    client = gemini_module.GeminiClient(api_key="test-key")
    response = SimpleNamespace(
        usage_metadata=SimpleNamespace(
            prompt_token_count=12,
            candidates_token_count=34,
            total_token_count=46,
        )
    )

    client._record_usage(response, stage="kg_entities", duration_ms=120.5)

    assert len(client.usage_log) == 1
    usage = client.usage_log[0]
    assert usage["stage"] == "kg_entities"
    assert usage["prompt_tokens"] == 12
    assert usage["output_tokens"] == 34
    assert usage["total_tokens"] == 46
    assert usage["duration_ms"] == 120.5
