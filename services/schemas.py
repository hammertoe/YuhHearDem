"""JSON schemas for structured output from Gemini."""

# Transcript schema for constrained decoding
TRANSCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_title": {
            "type": "string",
            "description": "Full session title from the order paper",
        },
        "agenda_items": {
            "type": "array",
            "description": "Agenda items with speeches",
            "items": {
                "type": "object",
                "properties": {
                    "topic_title": {
                        "type": "string",
                        "description": "Title of the agenda item",
                    },
                    "speech_blocks": {
                        "type": "array",
                        "description": "Speeches by different speakers on this topic",
                        "items": {
                            "type": "object",
                            "properties": {
                                "speaker_name": {
                                    "type": "string",
                                    "description": "Name of the speaker as mentioned in the video",
                                },
                                "sentences": {
                                    "type": "array",
                                    "description": "Individual sentences with timestamps",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "start_time": {
                                                "type": "string",
                                                "description": "Timestamp in XmYs format (e.g., '5m30s', '1h15m20s')",
                                            },
                                            "text": {
                                                "type": "string",
                                                "description": "The spoken text",
                                            },
                                        },
                                        "required": ["start_time", "text"],
                                    },
                                },
                            },
                            "required": ["speaker_name", "sentences"],
                        },
                    },
                },
                "required": ["topic_title", "speech_blocks"],
            },
        },
    },
    "required": ["session_title", "agenda_items"],
}

# Entity extraction schema
ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "description": "Entities extracted from the text",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Unique identifier (e.g., 'bill_cybercrime_2024', 'person_cummins')",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": [
                            "person",
                            "organization",
                            "place",
                            "law",
                            "concept",
                            "event",
                            "agenda_item",
                            "procedural_step",
                            "numeric_fact",
                            "policy_position",
                        ],
                        "description": "Type of entity",
                    },
                    "name": {
                        "type": "string",
                        "description": "Name as it appears in text",
                    },
                    "canonical_name": {
                        "type": "string",
                        "description": "Standardized name",
                    },
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative names/spellings",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of the entity",
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Importance score (0-1)",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Extraction confidence (0-1)",
                    },
                },
                "required": [
                    "entity_id",
                    "entity_type",
                    "name",
                    "canonical_name",
                ],
            },
        },
    },
    "required": ["entities"],
}

# Relationship extraction schema
RELATIONSHIP_SCHEMA = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "description": "Relationships between entities",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "ID of the source entity (must exist in entity list)",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "ID of the target entity (must exist in entity list or be a speaker)",
                    },
                    "relation_type": {
                        "type": "string",
                        "enum": [
                            "mentions",
                            "supports",
                            "opposes",
                            "relates_to",
                            "references",
                            "introduces",
                            "sponsors",
                            "questions",
                            "answers",
                            "rebuts",
                            "chairs",
                            "speaks_on",
                            "states",
                        ],
                        "description": "Type of relationship",
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                        "description": "Sentiment of the relationship",
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Direct quote from transcript supporting this relationship",
                    },
                    "evidence_timestamp": {
                        "type": "string",
                        "description": "Timestamp of the evidence in XmYs format",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score (0-1)",
                    },
                },
                "required": [
                    "source_id",
                    "target_id",
                    "relation_type",
                    "sentiment",
                    "evidence",
                ],
            },
        },
    },
    "required": ["relationships"],
}

# Chunk entity extraction schema (for processing small chunks)
CHUNK_ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "description": "Entities found in this chunk",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {
                        "type": "string",
                        "enum": [
                            "person",
                            "organization",
                            "place",
                            "law",
                            "concept",
                            "event",
                            "numeric_fact",
                            "policy_position",
                        ],
                    },
                    "name": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": {"type": "string"},
                    "mentions": {
                        "type": "array",
                        "description": "Where this entity is mentioned in this chunk",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sentence_index": {
                                    "type": "integer",
                                    "description": "Index of sentence in the chunk",
                                },
                                "context": {
                                    "type": "string",
                                    "description": "First 150 chars of the sentence",
                                },
                            },
                            "required": ["sentence_index"],
                        },
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": ["entity_id", "entity_type", "name", "canonical_name"],
            },
        },
    },
    "required": ["entities"],
}

# Chunk relationship extraction schema
CHUNK_RELATIONSHIP_SCHEMA = {
    "type": "object",
    "properties": {
        "relationships": {
            "type": "array",
            "description": "Relationships found in this chunk",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "relation_type": {
                        "type": "string",
                        "enum": [
                            "mentions",
                            "supports",
                            "opposes",
                            "relates_to",
                            "references",
                            "questions",
                            "answers",
                            "states",
                        ],
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                    },
                    "evidence": {"type": "string"},
                    "evidence_sentence_index": {
                        "type": "integer",
                        "description": "Index of the sentence containing the evidence",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": [
                    "source_id",
                    "target_id",
                    "relation_type",
                    "sentiment",
                    "evidence",
                    "evidence_sentence_index",
                ],
            },
        },
    },
    "required": ["relationships"],
}

# Entity deduplication resolution schema
DEDUPLICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["merge", "keep_separate"],
            "description": "Whether to merge these entities or keep them separate",
        },
        "reasoning": {
            "type": "string",
            "description": "Explanation for the decision",
        },
        "merged_name": {
            "type": "string",
            "description": "If merging, the canonical name to use",
        },
        "merged_aliases": {
            "type": "array",
            "items": {"type": "string"},
            "description": "If merging, combined aliases from both entities",
        },
    },
    "required": ["decision", "reasoning"],
}
