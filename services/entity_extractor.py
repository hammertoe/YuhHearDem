"""Entity extraction service using Gemini API."""

from dataclasses import dataclass, field, is_dataclass
from typing import Any

from models.entity import Entity
from models.relationship import Relationship
from parsers.transcript_models import SessionTranscript
from services.gemini import GeminiClient

# Two-pass extraction schemas (optimized for quality)
ENTITY_ONLY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "description": "Extracted entities from the transcript with full context",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Unique identifier (e.g., 'caricom-org-001')",
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
                            "schedule_item",
                            "numeric_fact",
                            "policy_position",
                            "funding_status",
                        ],
                        "description": "Category of entity",
                    },
                    "entity_subtype": {
                        "type": "string",
                        "description": "Optional subtype (e.g., bill, act, mp, minister)",
                    },
                    "name": {"type": "string", "description": "Primary name as mentioned in text"},
                    "canonical_name": {
                        "type": "string",
                        "description": "Standardized form of the name",
                    },
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative names or variations mentioned",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief context about the entity from the transcript",
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Salience score (0-1) indicating prominence in discussion",
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score (0-1) for this entity",
                    },
                    "evidence": {
                        "type": "array",
                        "description": "Evidence quotes supporting this entity",
                        "items": {"type": "string"},
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Structured attributes for facts or schedules",
                        "properties": {
                            "value": {"type": "string"},
                            "date": {"type": "string"},
                            "time": {"type": "string"},
                            "amount": {"type": "string"},
                            "unit": {"type": "string"},
                            "subject": {"type": "string"},
                            "predicate": {"type": "string"},
                            "object": {"type": "string"},
                        },
                    },
                },
                "required": ["entity_id", "entity_type", "name", "canonical_name"],
            },
        }
    },
    "required": ["entities"],
}


RELATIONSHIP_ONLY_SCHEMA = {
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
                        "description": "Entity ID of the source (from Pass 1)",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Entity ID of the target (from Pass 1)",
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
                            "amends",
                            "chairs",
                            "reports_on",
                            "speaks_on",
                            "about",
                            "funds",
                            "allocates",
                            "sets_deadline",
                            "corrects",
                            "updates",
                            "prioritizes",
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
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score (0-1) for this relationship",
                    },
                },
                "required": ["source_id", "target_id", "relation_type", "sentiment", "evidence"],
            },
        }
    },
    "required": ["relationships"],
}


@dataclass
class ExtractionResult:
    """Result of entity extraction from a transcript."""

    session_id: str
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)


class EntityExtractor:
    """
    Extracts entities and relationships from parliamentary transcripts using Gemini.

    Uses structured output to ensure consistent entity extraction with
    proper relationships, sentiment analysis, and evidence citations.
    """

    def __init__(self, api_key: str | None = None, thinking_budget: int | None = None):
        """
        Initialize the entity extractor with Gemini client.

        Args:
            api_key: Optional Gemini API key (defaults to env)
            thinking_budget: Thinking budget for Gemini (0=no thinking, -1=model controls, None=default)
        """
        self.gemini_client = GeminiClient(api_key=api_key, thinking_budget=thinking_budget)

    # Extraction configuration
    MAX_TWO_PASS_SIZE_KB = 3500  # Gemini ~3.8 MB limit with safety margin

    def extract_from_transcript(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None,
        method: str = "auto",
    ) -> ExtractionResult:
        """
        Extract entities and relationships from a transcript.

        By default uses two-pass approach for better quality. Falls back to
        agenda-item chunking for extremely large transcripts (>3.5 MB).

        Args:
            transcript: Session transcript to analyze
            seed_entities: Optional spaCy-detected entities for grounding
            method: Extraction method - "auto" (default), "two-pass", or "chunked"

        Returns:
            ExtractionResult with extracted entities and relationships
        """
        import json

        # Check transcript size
        transcript_json = json.dumps(self._serialize_transcript(transcript), indent=2)
        transcript_size_kb = len(transcript_json) / 1024

        # Determine method
        if method == "auto":
            if transcript_size_kb > self.MAX_TWO_PASS_SIZE_KB:
                print(
                    f"   📦 Very large transcript ({transcript_size_kb:.1f} KB) - using chunked extraction..."
                )
                method = "chunked"
            else:
                print(
                    f"   📄 Transcript size: {transcript_size_kb:.1f} KB - using two-pass extraction..."
                )
                method = "two-pass"

        if method == "two-pass":
            return self._extract_two_pass(transcript, seed_entities)
        if method == "chunked":
            if len(transcript.agenda_items) < 2:
                raise ValueError(
                    "Chunked extraction requires multiple agenda items. "
                    "Use method='two-pass' or split the transcript."
                )
            print(f"   📦 Processing {len(transcript.agenda_items)} agenda items separately...")
            return self._extract_chunked(transcript, seed_entities)
        raise ValueError(
            f"Unknown extraction method: {method}. Use 'auto', 'two-pass', or 'chunked'."
        )

    def _extract_chunked(
        self, transcript: SessionTranscript, seed_entities: list[dict] | None = None
    ) -> ExtractionResult:
        """
        Extract entities by processing each agenda item separately, then merging.

        Args:
            transcript: Session transcript with multiple agenda items
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            Merged ExtractionResult with all entities and relationships
        """
        session_id = f"{transcript.chamber}-{transcript.date.isoformat()}"
        all_entities = []
        all_relationships = []

        for i, agenda_item in enumerate(transcript.agenda_items, 1):
            print(
                f"      Chunk {i}/{len(transcript.agenda_items)}: {agenda_item.topic_title[:60]}..."
            )

            # Create a partial transcript with just this agenda item
            chunk_transcript = SessionTranscript(
                session_title=transcript.session_title,
                date=transcript.date,
                agenda_items=[agenda_item],
                chamber=transcript.chamber,
                video_url=transcript.video_url,
                video_title=transcript.video_title,
                video_upload_date=transcript.video_upload_date,
            )

            # Extract from this chunk
            try:
                chunk_result = self._extract_two_pass(chunk_transcript, seed_entities)
                all_entities.extend(chunk_result.entities)
                all_relationships.extend(chunk_result.relationships)
                print(
                    f"         ✓ Found {len(chunk_result.entities)} entities, {len(chunk_result.relationships)} relationships"
                )
            except Exception as e:
                print(f"         ⚠️  Chunk {i} failed: {e}")
                # Continue with other chunks

        # Merge results
        return ExtractionResult(
            session_id=session_id, entities=all_entities, relationships=all_relationships
        )

    def batch_extract(self, transcripts: list[SessionTranscript]) -> list[ExtractionResult]:
        """
        Extract entities from multiple transcripts.

        Args:
            transcripts: List of transcripts to process

        Returns:
            List of extraction results
        """
        results = []
        for transcript in transcripts:
            result = self.extract_from_transcript(transcript)
            results.append(result)
        return results

    def _extract_two_pass(
        self, transcript: SessionTranscript, seed_entities: list[dict] | None = None
    ) -> ExtractionResult:
        """
        Extract entities and relationships using two-pass approach for better quality.

        Pass 1: Extract all entities with full context (no chunking)
        Pass 2: Extract all relationships using complete entity list

        This approach eliminates entity fragmentation and produces more consistent
        results with fewer API calls.

        Args:
            transcript: Session transcript to analyze
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            ExtractionResult with extracted entities and relationships
        """
        session_id = f"{transcript.chamber}-{transcript.date.isoformat()}"

        print("   🔄 Two-pass extraction (Pass 1: Entities, Pass 2: Relationships)")

        # Pass 1: Extract entities with full context
        entities = self._extract_entities_pass1(transcript, seed_entities, session_id)
        print(f"   ✓ Pass 1 complete: {len(entities)} entities extracted")

        # Pass 2: Extract relationships using full entity list
        relationships = self._extract_relationships_pass2(transcript, entities, session_id)
        print(f"   ✓ Pass 2 complete: {len(relationships)} relationships extracted")

        return ExtractionResult(
            session_id=session_id, entities=entities, relationships=relationships
        )

    def _extract_entities_pass1(
        self, transcript: SessionTranscript, seed_entities: list[dict] | None, session_id: str
    ) -> list[Entity]:
        """
        Pass 1: Extract all entities from full transcript with seed entity context.

        Args:
            transcript: Full transcript to analyze
            seed_entities: Optional spaCy-detected entities for grounding
            session_id: Session identifier

        Returns:
            List of Entity objects with mentions
        """

        # Build entity-focused prompt
        prompt = self._build_entity_extraction_prompt(seed_entities)

        # Convert transcript to dict
        transcript_data = self._serialize_transcript(transcript)

        # Get structured extraction from Gemini (entities only)
        result = self.gemini_client.extract_entities_and_concepts(
            transcript_data=transcript_data,
            prompt=prompt,
            response_schema=ENTITY_ONLY_SCHEMA,
            stage="kg_entities",
        )

        # Parse result into entity objects
        entities = self._parse_entities(result["entities"], transcript, session_id)
        speaker_entities = self._extract_speaker_entities(transcript)
        entities = self._merge_entities(entities, speaker_entities)

        return entities

    def _extract_relationships_pass2(
        self, transcript: SessionTranscript, entities: list[Entity], session_id: str
    ) -> list[Relationship]:
        """
        Pass 2: Extract all relationships using complete entity list from Pass 1.

        Args:
            transcript: Full transcript to analyze
            entities: Complete list of entities from Pass 1
            session_id: Session identifier

        Returns:
            List of Relationship objects
        """

        # Build relationship-focused prompt with entity list
        prompt = self._build_relationship_extraction_prompt(entities)

        # Convert transcript to dict
        transcript_data = self._serialize_transcript(transcript)

        # Get structured extraction from Gemini (relationships only)
        result = self.gemini_client.extract_entities_and_concepts(
            transcript_data=transcript_data,
            prompt=prompt,
            response_schema=RELATIONSHIP_ONLY_SCHEMA,
            stage="kg_relationships",
        )

        # Parse result into relationship objects
        relationships = self._parse_relationships(result["relationships"], transcript, session_id)

        return relationships

    def _build_entity_extraction_prompt(self, seed_entities: list[dict] | None) -> str:
        """
        Build entity-focused prompt for Pass 1 extraction.

        Args:
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            Prompt string for entity-only extraction
        """
        prompt = """Extract ALL entities from this parliamentary transcript with full context.

For each entity:
- Assign a unique entity_id (slug-like and stable across sessions; e.g., "caricom-org-001")
- Determine the entity_type: person, organization, place, law, concept, event, agenda_item,
  procedural_step, schedule_item, numeric_fact, policy_position, or funding_status
- If applicable, set entity_subtype (e.g., bill, act, regulation, mp, minister, committee)
- Provide the name as mentioned in the text
- Provide a canonical_name (standardized form)
- List any aliases or variations mentioned throughout the transcript
- Provide a brief description of the entity based on context from the transcript
- Assign an importance score (0-1) based on prominence in discussion
- Assign a confidence score (0-1) indicating certainty in this entity
- Provide 1-3 evidence quotes for each entity
- Provide structured attributes for facts (numbers, dates, times, subjects, predicates, objects)

Focus on extracting:
1. Laws and bills being discussed
2. Organizations mentioned (CARICOM, government bodies, etc.)
3. Places and countries
4. Key concepts and topics
5. Events or initiatives
6. People mentioned (beyond the speakers themselves)
7. Procedural steps (readings, committee stage, votes)
8. Schedule items (next sitting date/time)
9. Numeric facts (counts, quantities, monetary amounts)
10. Policy positions and funding status statements

IMPORTANT:
- Use the FULL transcript context to create complete entity profiles
- Ensure entity_id is unique and consistent across all mentions
- Merge multiple mentions of the same entity into ONE entry with all aliases
"""

        # Add seed entities if provided
        if seed_entities:
            import json

            prompt += (
                "\n\nKnown entities from pre-processing (use these IDs if the entity matches):\n"
            )
            prompt += json.dumps(seed_entities, indent=2)
            prompt += "\n\nUse these pre-detected entities as a starting point, but also extract any additional entities found in the transcript."

        return prompt

    def _build_relationship_extraction_prompt(self, entities: list[Entity]) -> str:
        """
        Build relationship-focused prompt for Pass 2 extraction.

        Args:
            entities: Complete list of entities from Pass 1

        Returns:
            Prompt string for relationship-only extraction
        """
        import json

        # Convert entities to simplified dict for prompt
        entity_list = []
        for entity in entities:
            entity_list.append(
                {
                    "entity_id": entity.entity_id,
                    "name": entity.canonical_name,
                    "type": self._normalize_entity_type(entity.entity_type),
                }
            )

        prompt = f"""Extract ALL relationships between entities from this parliamentary transcript.

You must ONLY use entity IDs from this complete list of entities:

{json.dumps(entity_list, indent=2)}

For each relationship:
- Use ONLY entity_id values from the list above for source_id and target_id
- Use speaker_id for speaker references (these are provided in the transcript)
 - Determine relation_type: mentions, supports, opposes, relates_to, references, introduces, sponsors, questions, answers, rebuts, amends, chairs, reports_on, speaks_on, about, funds, allocates, sets_deadline, corrects, updates, prioritizes, or states
- Determine sentiment: positive, negative, or neutral
- Provide evidence (direct quote from transcript that demonstrates this relationship)
- Assign a confidence score (0-1) for how certain you are about this relationship

Focus on extracting:
1. Which speakers mention which entities (speaker → entity)
2. Support/opposition relationships (entity → entity, or speaker → entity)
3. Thematic connections between entities (entity → entity)
4. References to laws, bills, or policies (entity → entity)
5. Organizational affiliations (person → organization, organization → organization)

IMPORTANT:
- ONLY create relationships between entities that exist in the provided entity list
- Validate that both source_id and target_id exist in the list above
- Use the FULL transcript context to identify all relationships
- Include cross-agenda relationships (entities mentioned in different sections)
"""

        return prompt

    def _parse_entities(
        self, entity_dicts: list[dict], transcript: SessionTranscript, session_id: str
    ) -> list[Entity]:
        """
        Parse entity dictionaries into Entity objects with mention locations.

        Args:
            entity_dicts: Raw entity dictionaries from Gemini
            transcript: Original transcript for finding mentions
            session_id: Session identifier

        Returns:
            List of Entity objects with mentions
        """
        entities = []

        for entity_dict in entity_dicts:
            entity = Entity(
                entity_id=entity_dict["entity_id"],
                entity_type=entity_dict["entity_type"],
                entity_subtype=entity_dict.get("entity_subtype"),
                name=entity_dict["name"],
                canonical_name=entity_dict["canonical_name"],
                aliases=entity_dict.get("aliases", []),
                description=entity_dict.get("description"),
                importance_score=entity_dict.get("importance", 0.0),
                entity_confidence=entity_dict.get("confidence"),
                source="llm",
                source_ref=session_id,
            )
            attributes = entity_dict.get("attributes")
            evidence = entity_dict.get("evidence")
            if attributes or evidence:
                entity.meta_data = {}
                if attributes:
                    entity.meta_data["attributes"] = attributes
                if evidence:
                    entity.meta_data["evidence"] = evidence
            entities.append(entity)

        return entities

    def _parse_relationships(
        self, rel_dicts: list[dict], transcript: SessionTranscript, session_id: str
    ) -> list[Relationship]:
        """
        Parse relationship dictionaries into Relationship objects.

        Args:
            rel_dicts: Raw relationship dictionaries from Gemini
            transcript: Original transcript for context
            session_id: Session identifier

        Returns:
            List of Relationship objects
        """
        relationships = []

        for rel_dict in rel_dicts:
            # Find timestamp from evidence quote
            timestamp = self._find_evidence_timestamp(rel_dict["evidence"], transcript)

            relationship = Relationship(
                source_id=rel_dict["source_id"],
                target_id=rel_dict["target_id"],
                relation_type=rel_dict["relation_type"],
                sentiment=rel_dict.get("sentiment"),
                evidence=rel_dict["evidence"],
                confidence=rel_dict.get("confidence"),
                source="llm",
                source_ref=session_id,
                timestamp_seconds=timestamp,
            )
            relationships.append(relationship)

        return relationships

    def _find_evidence_timestamp(self, evidence: str, transcript: SessionTranscript) -> int | None:
        """
        Find the timestamp of evidence quote in transcript.

        Args:
            evidence: Quote from transcript
            transcript: Transcript to search

        Returns:
            Timestamp string or empty string if not found
        """
        evidence_lower = evidence.lower()

        for agenda in transcript.agenda_items:
            for speech in agenda.speech_blocks:
                for sentence in speech.sentences:
                    if evidence_lower in sentence.text.lower():
                        return self._parse_timecode(sentence.start_time)

        return None  # Not found

    def _serialize_transcript(self, transcript: SessionTranscript) -> dict[str, Any]:
        model_dump = getattr(transcript, "model_dump", None)
        if callable(model_dump):
            data = model_dump()
            return data if isinstance(data, dict) else {}
        to_dict = getattr(transcript, "to_dict", None)
        if callable(to_dict):
            data = to_dict()
            return data if isinstance(data, dict) else {}
        if is_dataclass(transcript):
            from dataclasses import asdict

            data = self._normalize_json(asdict(transcript))
            return data if isinstance(data, dict) else {}
        return {}

    def _normalize_json(self, payload):
        from datetime import date, datetime

        if isinstance(payload, datetime):
            return payload.isoformat()
        if isinstance(payload, date):
            return payload.isoformat()
        if isinstance(payload, list):
            return [self._normalize_json(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._normalize_json(value) for key, value in payload.items()}
        return payload

    def _normalize_entity_type(self, entity_type: Any) -> str:
        if hasattr(entity_type, "value"):
            return str(getattr(entity_type, "value"))
        return str(entity_type)

    def _extract_speaker_entities(self, transcript: SessionTranscript) -> list[Entity]:
        speakers: dict[str, str] = {}
        for agenda in transcript.agenda_items:
            for speech in agenda.speech_blocks:
                if not speech.speaker_id:
                    continue
                speakers[speech.speaker_id] = speech.speaker_name

        speaker_entities = []
        for speaker_id, speaker_name in speakers.items():
            speaker_entities.append(
                Entity(
                    entity_id=speaker_id,
                    entity_type="person",
                    entity_subtype="speaker",
                    name=speaker_name,
                    canonical_name=speaker_name,
                    aliases=[],
                    description="Parliamentary speaker",
                    importance_score=1.0,
                    entity_confidence=1.0,
                    source="derived",
                    source_ref=f"{transcript.chamber}-{transcript.date.isoformat()}",
                    speaker_canonical_id=speaker_id,
                )
            )
        return speaker_entities

    def _merge_entities(self, entities: list[Entity], additions: list[Entity]) -> list[Entity]:
        existing_ids = {entity.entity_id for entity in entities}
        for entity in additions:
            if entity.entity_id not in existing_ids:
                entities.append(entity)
                existing_ids.add(entity.entity_id)
        return entities

    def _parse_timecode(self, time_str: str) -> int:
        import re

        match = re.match(r"(\d+)m(\d+)s(\d+)ms", time_str)
        if not match:
            return 0
        minutes, seconds, ms = map(int, match.groups())
        return minutes * 60 + seconds
