"""Entity extraction speaker handling tests."""

from datetime import datetime, timezone

from parsers.transcript_models import Sentence, SessionTranscript, SpeechBlock, TranscriptAgendaItem
from services import entity_extractor as entity_extractor_module


class DummyGeminiClient:
    """Stub Gemini client for extraction tests."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    def extract_entities_and_concepts(self, transcript_data, prompt, response_schema=None):
        if response_schema and "entities" in response_schema.get("properties", {}):
            return {"entities": []}
        return {"relationships": []}


def test_extract_from_transcript_adds_speaker_entities(monkeypatch):
    """Speakers should be promoted to first-class entities."""

    class DummyGeminiClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract_entities_and_concepts(
            self, transcript_data, prompt, response_schema=None, **kwargs
        ):
            if response_schema and "entities" in response_schema.get("properties", {}):
                return {
                    "entities": [
                        {
                            "entity_id": "speaker-123",
                            "entity_type": "person",
                            "name": "Hon. Jane Doe",
                            "canonical_name": "Hon. Jane Doe",
                            "aliases": [],
                        }
                    ]
                }
            return {"relationships": []}

    monkeypatch.setattr(entity_extractor_module, "GeminiClient", DummyGeminiClient)

    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Opening",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Jane Doe",
                        speaker_id="speaker-123",
                        sentences=[Sentence(start_time="0m0s0ms", text="Welcome.")],
                    )
                ],
            )
        ],
    )

    extractor = entity_extractor_module.EntityExtractor()
    result = extractor.extract_from_transcript(transcript, method="two-pass")

    assert any(
        entity.entity_id == "speaker-123" and entity.entity_type == "person"
        for entity in result.entities
    )


def test_entity_extractor_accepts_api_key(monkeypatch):
    """EntityExtractor should pass api_key to Gemini client."""
    captured = {}

    class DummyGeminiClient:
        def __init__(self, api_key=None, thinking_budget=None):
            captured["api_key"] = api_key

        def extract_entities_and_concepts(
            self, transcript_data, prompt, response_schema=None, stage="kg_extraction"
        ):
            pass
            return {"relationships": []}

    monkeypatch.setattr(entity_extractor_module, "GeminiClient", DummyGeminiClient)

    entity_extractor_module.EntityExtractor(api_key="test-key")

    assert captured["api_key"] == "test-key"


def test_extract_from_transcript_handles_mentions(monkeypatch):
    """Entity extraction should not fail when mentions exist."""

    class DummyGeminiClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def extract_entities_and_concepts(
            self, transcript_data, prompt, response_schema=None, stage="kg_extraction"
        ):
            if response_schema and "entities" in response_schema.get("properties", {}):
                return {
                    "entities": [
                        {
                            "entity_id": "concept-1",
                            "entity_type": "concept",
                            "name": "Budget",
                            "canonical_name": "Budget",
                            "aliases": [],
                        }
                    ]
                }
            return {"relationships": []}

    monkeypatch.setattr(entity_extractor_module, "GeminiClient", DummyGeminiClient)

    transcript = SessionTranscript(
        session_title="Test Session",
        date=datetime.now(timezone.utc).replace(tzinfo=None),
        chamber="house",
        agenda_items=[
            TranscriptAgendaItem(
                topic_title="Opening",
                speech_blocks=[
                    SpeechBlock(
                        speaker_name="Hon. Jane Doe",
                        speaker_id="speaker-123",
                        sentences=[Sentence(start_time="0m0s0ms", text="Budget details.")],
                    )
                ],
            )
        ],
    )

    extractor = entity_extractor_module.EntityExtractor()
    result = extractor.extract_from_transcript(transcript, method="two-pass")

    entity_ids = {entity.entity_id for entity in result.entities}

    assert "concept-1" in entity_ids
    assert "speaker-123" in entity_ids
