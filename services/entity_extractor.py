"""Entity extraction service using Gemini API."""

from dataclasses import dataclass, field
from typing import Optional

from src.models.entity import Entity, EntityType, Mention, Relationship, RelationType, Sentiment
from src.models.session import SessionTranscript
from src.services.gemini import GeminiClient


# Gemini structured output schema for entity extraction (combined - legacy)
ENTITY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "description": "Extracted entities from the transcript",
            "items": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["person", "organization", "place", "law", "concept", "event"]
                    },
                    "name": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["entity_id", "entity_type", "name", "canonical_name"]
            }
        },
        "relationships": {
            "type": "array",
            "description": "Relationships between entities",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "relation_type": {
                        "type": "string",
                        "enum": ["mentions", "supports", "opposes", "relates_to", "references"]
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"]
                    },
                    "evidence": {"type": "string"}
                },
                "required": ["source_id", "target_id", "relation_type", "sentiment", "evidence"]
            }
        }
    },
    "required": ["entities", "relationships"]
}


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
                    "entity_id": {"type": "string", "description": "Unique identifier (e.g., 'caricom-org-001')"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["person", "organization", "place", "law", "concept", "event"],
                        "description": "Category of entity"
                    },
                    "name": {"type": "string", "description": "Primary name as mentioned in text"},
                    "canonical_name": {"type": "string", "description": "Standardized form of the name"},
                    "aliases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative names or variations mentioned"
                    },
                    "description": {"type": "string", "description": "Brief context about the entity from the transcript"},
                    "importance": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Salience score (0-1) indicating prominence in discussion"
                    }
                },
                "required": ["entity_id", "entity_type", "name", "canonical_name"]
            }
        }
    },
    "required": ["entities"]
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
                    "source_id": {"type": "string", "description": "Entity ID of the source (from Pass 1)"},
                    "target_id": {"type": "string", "description": "Entity ID of the target (from Pass 1)"},
                    "relation_type": {
                        "type": "string",
                        "enum": ["mentions", "supports", "opposes", "relates_to", "references"],
                        "description": "Type of relationship"
                    },
                    "sentiment": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral"],
                        "description": "Sentiment of the relationship"
                    },
                    "evidence": {"type": "string", "description": "Direct quote from transcript supporting this relationship"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Confidence score (0-1) for this relationship"
                    }
                },
                "required": ["source_id", "target_id", "relation_type", "sentiment", "evidence"]
            }
        }
    },
    "required": ["relationships"]
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

    def __init__(self, thinking_budget: Optional[int] = None):
        """
        Initialize the entity extractor with Gemini client.

        Args:
            thinking_budget: Thinking budget for Gemini (0=no thinking, -1=model controls, None=default)
        """
        self.gemini_client = GeminiClient(thinking_budget=thinking_budget)

    # Chunking configuration
    MAX_TRANSCRIPT_SIZE_KB = 100  # Process in chunks if larger than this (legacy)
    MAX_TWO_PASS_SIZE_KB = 3500  # Maximum size for two-pass (Gemini ~3.8 MB limit with safety margin)

    def extract_from_transcript(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None,
        method: str = "auto"
    ) -> ExtractionResult:
        """
        Extract entities and relationships from a transcript.

        By default uses two-pass approach for better quality. Falls back to
        chunking for extremely large transcripts (>3.5 MB).

        Args:
            transcript: Session transcript to analyze
            seed_entities: Optional spaCy-detected entities for grounding
            method: Extraction method - "auto" (default), "two-pass", or "chunked"

        Returns:
            ExtractionResult with extracted entities and relationships
        """
        import json

        # Check transcript size
        transcript_json = json.dumps(transcript.to_dict(), indent=2)
        transcript_size_kb = len(transcript_json) / 1024

        # Determine method
        if method == "auto":
            # Use two-pass for all transcripts under 3.5 MB (safety margin)
            # Fall back to chunking for extremely large transcripts
            if transcript_size_kb > self.MAX_TWO_PASS_SIZE_KB:
                print(f"   📦 Very large transcript ({transcript_size_kb:.1f} KB) - using chunked extraction...")
                method = "chunked"
            else:
                print(f"   📄 Transcript size: {transcript_size_kb:.1f} KB - using two-pass extraction...")
                method = "two-pass"

        # Execute based on method
        if method == "two-pass":
            return self._extract_two_pass(transcript, seed_entities)
        elif method == "chunked":
            # For chunked mode, check if we need to chunk by agenda items
            if transcript_size_kb > self.MAX_TRANSCRIPT_SIZE_KB and len(transcript.agenda_items) > 1:
                print(f"   📦 Processing {len(transcript.agenda_items)} agenda items separately...")
                return self._extract_chunked(transcript, seed_entities)
            else:
                return self._extract_single(transcript, seed_entities)
        else:
            raise ValueError(f"Unknown extraction method: {method}. Use 'auto', 'two-pass', or 'chunked'.")

    def _extract_single(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None
    ) -> ExtractionResult:
        """
        Extract entities from a single transcript chunk (legacy chunked mode).

        Checks if the chunk is still too large for processing. If it has a single
        oversized agenda item with multiple speech blocks, delegates to nested
        speech block chunking.

        Args:
            transcript: Session transcript to analyze
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            ExtractionResult with extracted entities and relationships
        """
        import json

        # Check if this chunk is still too large
        transcript_json = json.dumps(transcript.to_dict(), indent=2)
        transcript_size_kb = len(transcript_json) / 1024

        # If we have one large agenda item with multiple speech blocks, chunk by speech blocks
        if (transcript_size_kb > self.MAX_TRANSCRIPT_SIZE_KB and
            len(transcript.agenda_items) == 1 and
            len(transcript.agenda_items[0].speech_blocks) > 1):
            # Nested chunking by speech blocks
            return self._extract_by_speech_blocks(transcript, seed_entities)

        # Filter seed entities to only those relevant to this chunk
        if seed_entities:
            chunk_text = self._get_chunk_text(transcript)
            filtered_seeds = self._filter_relevant_seeds(seed_entities, chunk_text)
            if filtered_seeds:
                print(f"         🔍 Filtered seeds: {len(seed_entities)} → {len(filtered_seeds)} relevant entities")
            seed_entities = filtered_seeds

        # Otherwise process normally
        # Build prompt for Gemini
        prompt = self._build_extraction_prompt()

        # Convert transcript to dict for Gemini
        transcript_data = transcript.to_dict()

        # Get structured extraction from Gemini
        result = self.gemini_client.extract_entities_and_concepts(
            transcript_data=transcript_data,
            prompt=prompt,
            response_schema=ENTITY_EXTRACTION_SCHEMA
        )

        # Parse result into entity and relationship objects
        session_id = f"{transcript.chamber}-{transcript.date.isoformat()}"

        entities = self._parse_entities(result["entities"], transcript, session_id)
        relationships = self._parse_relationships(result["relationships"], transcript, session_id)

        return ExtractionResult(
            session_id=session_id,
            entities=entities,
            relationships=relationships
        )

    def _extract_chunked(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None
    ) -> ExtractionResult:
        """
        Extract entities by processing each agenda item separately, then merging (legacy mode).

        Args:
            transcript: Session transcript with multiple agenda items
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            Merged ExtractionResult with all entities and relationships
        """
        from src.models.session import SessionTranscript

        session_id = f"{transcript.chamber}-{transcript.date.isoformat()}"
        all_entities = []
        all_relationships = []

        for i, agenda_item in enumerate(transcript.agenda_items, 1):
            print(f"      Chunk {i}/{len(transcript.agenda_items)}: {agenda_item.topic_title[:60]}...")

            # Create a partial transcript with just this agenda item
            chunk_transcript = SessionTranscript(
                session_title=transcript.session_title,
                date=transcript.date,
                agenda_items=[agenda_item],
                chamber=transcript.chamber,
                video_url=transcript.video_url,
                video_title=transcript.video_title,
                video_upload_date=transcript.video_upload_date
            )

            # Filter seed entities to only those relevant to this chunk
            chunk_seeds = seed_entities
            if seed_entities:
                chunk_text = self._get_chunk_text(chunk_transcript)
                chunk_seeds = self._filter_relevant_seeds(seed_entities, chunk_text)

            # Extract from this chunk
            try:
                chunk_result = self._extract_single(chunk_transcript, chunk_seeds)
                all_entities.extend(chunk_result.entities)
                all_relationships.extend(chunk_result.relationships)
                print(f"         ✓ Found {len(chunk_result.entities)} entities, {len(chunk_result.relationships)} relationships")
            except Exception as e:
                print(f"         ⚠️  Chunk {i} failed: {e}")
                # Continue with other chunks

        # Merge results
        return ExtractionResult(
            session_id=session_id,
            entities=all_entities,
            relationships=all_relationships
        )

    def _extract_by_speech_blocks(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None
    ) -> ExtractionResult:
        """
        Extract entities by processing each speech block separately (nested chunking - legacy).

        Used when a single agenda item is too large. Processes each speaker's
        contribution individually to avoid response truncation.

        Args:
            transcript: Session transcript with one large agenda item
            seed_entities: Optional spaCy-detected entities for context

        Returns:
            Merged ExtractionResult with all entities and relationships
        """
        from src.models.session import SessionTranscript, TranscriptAgendaItem

        session_id = f"{transcript.chamber}-{transcript.date.isoformat()}"
        all_entities = []
        all_relationships = []

        # Should only have one agenda item
        if len(transcript.agenda_items) != 1:
            raise ValueError("_extract_by_speech_blocks expects exactly one agenda item")

        agenda_item = transcript.agenda_items[0]
        speech_blocks = agenda_item.speech_blocks

        print(f"         📦 Nested chunking: {len(speech_blocks)} speech blocks")

        for i, speech_block in enumerate(speech_blocks, 1):
            speaker_preview = speech_block.speaker_name[:40]
            print(f"            Speech block {i}/{len(speech_blocks)}: {speaker_preview}...")

            # Create a partial agenda item with just this speech block
            partial_agenda_item = TranscriptAgendaItem(
                topic_title=agenda_item.topic_title,
                speech_blocks=[speech_block],
                bill_id=agenda_item.bill_id,
                bill_match_confidence=agenda_item.bill_match_confidence
            )

            # Create a partial transcript with this single speech block
            chunk_transcript = SessionTranscript(
                session_title=transcript.session_title,
                date=transcript.date,
                agenda_items=[partial_agenda_item],
                chamber=transcript.chamber,
                video_url=transcript.video_url,
                video_title=transcript.video_title,
                video_upload_date=transcript.video_upload_date
            )

            # Filter seed entities to only those relevant to this speech block
            block_seeds = seed_entities
            if seed_entities:
                block_text = self._get_chunk_text(chunk_transcript)
                block_seeds = self._filter_relevant_seeds(seed_entities, block_text)

            # Extract from this speech block chunk
            try:
                chunk_result = self._extract_single(chunk_transcript, block_seeds)
                all_entities.extend(chunk_result.entities)
                all_relationships.extend(chunk_result.relationships)
                print(f"               ✓ Found {len(chunk_result.entities)} entities, {len(chunk_result.relationships)} relationships")
            except Exception as e:
                print(f"               ⚠️  Speech block {i} failed: {e}")
                # Continue with other speech blocks

        # Merge results
        return ExtractionResult(
            session_id=session_id,
            entities=all_entities,
            relationships=all_relationships
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
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None = None
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

        print(f"   🔄 Two-pass extraction (Pass 1: Entities, Pass 2: Relationships)")

        # Pass 1: Extract entities with full context
        entities = self._extract_entities_pass1(transcript, seed_entities, session_id)
        print(f"   ✓ Pass 1 complete: {len(entities)} entities extracted")

        # Pass 2: Extract relationships using full entity list
        relationships = self._extract_relationships_pass2(transcript, entities, session_id)
        print(f"   ✓ Pass 2 complete: {len(relationships)} relationships extracted")

        return ExtractionResult(
            session_id=session_id,
            entities=entities,
            relationships=relationships
        )

    def _extract_entities_pass1(
        self,
        transcript: SessionTranscript,
        seed_entities: list[dict] | None,
        session_id: str
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
        import json

        # Build entity-focused prompt
        prompt = self._build_entity_extraction_prompt(seed_entities)

        # Convert transcript to dict
        transcript_data = transcript.to_dict()

        # Get structured extraction from Gemini (entities only)
        result = self.gemini_client.extract_entities_and_concepts(
            transcript_data=transcript_data,
            prompt=prompt,
            response_schema=ENTITY_ONLY_SCHEMA
        )

        # Parse result into entity objects
        entities = self._parse_entities(
            result["entities"],
            transcript,
            session_id
        )

        return entities

    def _extract_relationships_pass2(
        self,
        transcript: SessionTranscript,
        entities: list[Entity],
        session_id: str
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
        import json

        # Build relationship-focused prompt with entity list
        prompt = self._build_relationship_extraction_prompt(entities)

        # Convert transcript to dict
        transcript_data = transcript.to_dict()

        # Get structured extraction from Gemini (relationships only)
        result = self.gemini_client.extract_entities_and_concepts(
            transcript_data=transcript_data,
            prompt=prompt,
            response_schema=RELATIONSHIP_ONLY_SCHEMA
        )

        # Parse result into relationship objects
        relationships = self._parse_relationships(
            result["relationships"],
            transcript,
            session_id
        )

        return relationships

    def _build_extraction_prompt(self) -> str:
        """
        Build prompt for Gemini entity extraction.

        Returns:
            Prompt string for entity extraction
        """
        prompt = """Extract entities and relationships from this parliamentary transcript.

For each entity:
- Assign a unique entity_id (e.g., "caricom-org-001")
- Determine the entity_type: person, organization, place, law, concept, or event
- Provide the name as mentioned in the text
- Provide a canonical_name (standardized form)
- List any aliases or variations mentioned

For each relationship:
- Use speaker_id for speaker references (use the IDs provided in the transcript)
- Use entity_id for entity references
- Determine relation_type: mentions, supports, opposes, relates_to, or references
- Determine sentiment: positive, negative, or neutral
- Provide evidence (direct quote from transcript)

Focus on extracting:
1. Laws and bills being discussed
2. Organizations mentioned (CARICOM, government bodies, etc.)
3. Places and countries
4. Key concepts and topics
5. Events or initiatives
6. Relationships showing support, opposition, or thematic connections

Extract all significant entities and relationships from the provided transcript data."""

        return prompt

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
- Assign a unique entity_id (e.g., "caricom-org-001")
- Determine the entity_type: person, organization, place, law, concept, or event
- Provide the name as mentioned in the text
- Provide a canonical_name (standardized form)
- List any aliases or variations mentioned throughout the transcript
- Provide a brief description of the entity based on context from the transcript
- Assign an importance score (0-1) based on prominence in discussion

Focus on extracting:
1. Laws and bills being discussed
2. Organizations mentioned (CARICOM, government bodies, etc.)
3. Places and countries
4. Key concepts and topics
5. Events or initiatives
6. People mentioned (beyond the speakers themselves)

IMPORTANT:
- Use the FULL transcript context to create complete entity profiles
- Ensure entity_id is unique and consistent across all mentions
- Merge multiple mentions of the same entity into ONE entry with all aliases
"""

        # Add seed entities if provided
        if seed_entities:
            import json
            prompt += f"\n\nKnown entities from pre-processing (use these IDs if the entity matches):\n"
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
            entity_list.append({
                "entity_id": entity.entity_id,
                "name": entity.canonical_name,
                "type": entity.entity_type.value
            })

        prompt = f"""Extract ALL relationships between entities from this parliamentary transcript.

You must ONLY use entity IDs from this complete list of entities:

{json.dumps(entity_list, indent=2)}

For each relationship:
- Use ONLY entity_id values from the list above for source_id and target_id
- Use speaker_id for speaker references (these are provided in the transcript)
- Determine relation_type: mentions, supports, opposes, relates_to, or references
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
        self,
        entity_dicts: list[dict],
        transcript: SessionTranscript,
        session_id: str
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
            # Find mentions in transcript
            mentions = self._find_mentions(
                entity_dict["name"],
                entity_dict.get("aliases", []),
                transcript,
                session_id
            )

            entity = Entity(
                entity_id=entity_dict["entity_id"],
                entity_type=EntityType(entity_dict["entity_type"]),
                name=entity_dict["name"],
                canonical_name=entity_dict["canonical_name"],
                aliases=entity_dict.get("aliases", []),
                mentions=mentions
            )
            entities.append(entity)

        return entities

    def _parse_relationships(
        self,
        rel_dicts: list[dict],
        transcript: SessionTranscript,
        session_id: str
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
                relation_type=RelationType(rel_dict["relation_type"]),
                sentiment=Sentiment(rel_dict["sentiment"]),
                evidence=rel_dict["evidence"],
                session_id=session_id,
                timestamp=timestamp
            )
            relationships.append(relationship)

        return relationships

    def _find_mentions(
        self,
        name: str,
        aliases: list[str],
        transcript: SessionTranscript,
        session_id: str
    ) -> list[Mention]:
        """
        Find all mentions of an entity in the transcript.

        Args:
            name: Primary entity name
            aliases: Alternative names
            transcript: Transcript to search
            session_id: Session identifier

        Returns:
            List of Mention objects
        """
        mentions = []
        all_names = [name] + aliases

        for agenda_idx, agenda in enumerate(transcript.agenda_items):
            for speech in agenda.speech_blocks:
                for sent_idx, sentence in enumerate(speech.sentences):
                    # Check if any name variant appears in sentence
                    text_lower = sentence.text.lower()
                    for variant in all_names:
                        if variant.lower() in text_lower:
                            mention = Mention(
                                session_id=session_id,
                                agenda_item_index=agenda_idx,
                                sentence_index=sent_idx,
                                timestamp=sentence.start_time,
                                context=sentence.text[:150],  # First 150 chars
                                bill_id=agenda.bill_id  # Link to legislation database
                            )
                            mentions.append(mention)
                            break  # Only one mention per sentence

        return mentions

    def _find_evidence_timestamp(
        self,
        evidence: str,
        transcript: SessionTranscript
    ) -> str:
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
                        return sentence.start_time

        return ""  # Not found
