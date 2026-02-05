"""Tests for HybridGraphRAG heuristics."""

from services.hybrid_graphrag import HybridGraphRAG


def test_should_skip_llm_entity_extraction_for_short_lowercase_query():
    rag = HybridGraphRAG(kg_store=None, entity_extractor=None, embedding_service=None)

    assert rag._should_use_llm_entity_extraction("potholes") is False


def test_should_use_llm_entity_extraction_for_named_entities():
    rag = HybridGraphRAG(kg_store=None, entity_extractor=None, embedding_service=None)

    assert rag._should_use_llm_entity_extraction("Senator Cummins") is True
    assert rag._should_use_llm_entity_extraction("Road Traffic Act") is True


def test_should_skip_llm_entity_extraction_for_sentence_case_query():
    rag = HybridGraphRAG(kg_store=None, entity_extractor=None, embedding_service=None)

    assert rag._should_use_llm_entity_extraction("What has been discussed about potholes?") is False
