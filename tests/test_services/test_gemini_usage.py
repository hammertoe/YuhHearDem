"""Tests for Gemini usage accounting."""

from types import SimpleNamespace

from services import gemini as gemini_module


class DummyClient:
    """Stub Gemini API client."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.models: "DummyModels | None" = None


class DummyModels:
    """Stub models handler."""

    def __init__(self, response: SimpleNamespace) -> None:
        self._response = response

    def generate_content(self, model: str, contents, config):  # type: ignore[no-untyped-def]
        return self._response


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


def test_extract_entities_uses_parsed_response(monkeypatch):
    """Structured responses should use parsed payload when available."""
    parsed_payload = {"entities": [{"entity_id": "test-1"}]}
    response = SimpleNamespace(
        text="{not valid json}",
        parsed=parsed_payload,
        usage_metadata=None,
    )

    def dummy_client_factory(api_key: str):  # type: ignore[no-untyped-def]
        client = DummyClient(api_key=api_key)
        client.models = DummyModels(response)
        return client

    monkeypatch.setattr(gemini_module.genai, "Client", dummy_client_factory)

    client = gemini_module.GeminiClient(api_key="test-key")
    result = client.extract_entities_and_concepts(
        transcript_data={"session_title": "Test", "agenda_items": []},
        prompt="Extract entities",
        response_schema={"type": "object", "properties": {"entities": {"type": "array"}}},
    )

    assert result == parsed_payload
