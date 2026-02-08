"""Chunked transcript processing for entity extraction."""

import json
from dataclasses import dataclass, field
from typing import Any

from services.gemini import GeminiClient
from services.schemas import CHUNK_ENTITY_SCHEMA, CHUNK_RELATIONSHIP_SCHEMA


@dataclass
class Sentence:
    """A single sentence with timestamp."""

    start_time: str
    text: str


@dataclass
class SpeechBlock:
    """Speech by a single speaker."""

    speaker_name: str
    speaker_id: str | None = None
    sentences: list[Sentence] = field(default_factory=list)


@dataclass
class TranscriptChunk:
    """Chunk of transcript for processing."""

    chunk_index: int
    agenda_item_title: str
    sentences: list[Sentence]
    speaker_names: list[str]
    context_summary: str = ""  # Summary of previous chunks


@dataclass
class ChunkEntity:
    """Entity extracted from a chunk."""

    entity_id: str
    entity_type: str
    name: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    mentions: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    chunk_index: int = 0


@dataclass
class ChunkRelationship:
    """Relationship extracted from a chunk."""

    source_id: str
    target_id: str
    relation_type: str
    sentiment: str
    evidence: str
    evidence_sentence_index: int
    confidence: float = 0.0
    chunk_index: int = 0


class ChunkedTranscriptProcessor:
    """Process transcripts in chunks for better entity extraction."""

    def __init__(
        self,
        gemini_client: GeminiClient,
        chunk_size: int = 7,
        overlap: int = 2,
    ) -> None:
        """
        Initialize chunked processor.

        Args:
            gemini_client: Gemini client for extraction
            chunk_size: Number of sentences per chunk (default: 7)
            overlap: Number of overlapping sentences between chunks (default: 2)
        """
        self.client = gemini_client
        self.chunk_size = chunk_size
        self.overlap = overlap

    def create_chunks(
        self,
        agenda_item_title: str,
        speech_blocks: list[SpeechBlock],
    ) -> list[TranscriptChunk]:
        """
        Create chunks from speech blocks with overlap.

        Args:
            agenda_item_title: Title of the agenda item
            speech_blocks: List of speech blocks

        Returns:
            List of transcript chunks
        """
        # Flatten all sentences while tracking speakers
        all_sentences: list[tuple[Sentence, str]] = []
        for block in speech_blocks:
            for sentence in block.sentences:
                all_sentences.append((sentence, block.speaker_name))

        if not all_sentences:
            return []

        chunks = []
        context_summary = ""

        # Create overlapping chunks
        step = self.chunk_size - self.overlap
        for i in range(0, len(all_sentences), step):
            chunk_sentences = all_sentences[i : i + self.chunk_size]

            if not chunk_sentences:
                continue

            # Extract unique speakers in this chunk
            speakers = list(set(speaker for _, speaker in chunk_sentences))

            chunk = TranscriptChunk(
                chunk_index=len(chunks),
                agenda_item_title=agenda_item_title,
                sentences=[s for s, _ in chunk_sentences],
                speaker_names=speakers,
                context_summary=context_summary,
            )
            chunks.append(chunk)

            # Update context summary for next chunk
            context_summary = self._generate_context_summary(chunk)

        return chunks

    def extract_from_chunk(
        self,
        chunk: TranscriptChunk,
        existing_entities: list[ChunkEntity] | None = None,
    ) -> tuple[list[ChunkEntity], list[ChunkRelationship]]:
        """
        Extract entities and relationships from a single chunk.

        Args:
            chunk: Transcript chunk to process
            existing_entities: Entities from previous chunks (for context)

        Returns:
            Tuple of (entities, relationships)
        """
        # First pass: Extract entities
        entities = self._extract_entities_from_chunk(chunk, existing_entities)

        # Second pass: Extract relationships using the entities
        relationships = self._extract_relationships_from_chunk(chunk, entities)

        return entities, relationships

    def _extract_entities_from_chunk(
        self,
        chunk: TranscriptChunk,
        existing_entities: list[ChunkEntity] | None = None,
    ) -> list[ChunkEntity]:
        """Extract entities from chunk."""
        prompt = self._build_entity_extraction_prompt(chunk, existing_entities)

        result = self.client.generate_structured(
            prompt=prompt,
            response_schema=CHUNK_ENTITY_SCHEMA,
            stage="chunk_entity_extraction",
        )

        entities = []
        for entity_data in result.get("entities", []):
            entity = ChunkEntity(
                entity_id=entity_data["entity_id"],
                entity_type=entity_data["entity_type"],
                name=entity_data["name"],
                canonical_name=entity_data["canonical_name"],
                aliases=entity_data.get("aliases", []),
                description=entity_data.get("description", ""),
                mentions=entity_data.get("mentions", []),
                confidence=entity_data.get("confidence", 0.5),
                chunk_index=chunk.chunk_index,
            )
            entities.append(entity)

        return entities

    def _extract_relationships_from_chunk(
        self,
        chunk: TranscriptChunk,
        entities: list[ChunkEntity],
    ) -> list[ChunkRelationship]:
        """Extract relationships from chunk using entities."""
        prompt = self._build_relationship_extraction_prompt(chunk, entities)

        result = self.client.generate_structured(
            prompt=prompt,
            response_schema=CHUNK_RELATIONSHIP_SCHEMA,
            stage="chunk_relationship_extraction",
        )

        relationships = []
        entity_ids = {e.entity_id for e in entities}

        for rel_data in result.get("relationships", []):
            # Validate that source and target exist in our entity list
            source_id = rel_data["source_id"]
            target_id = rel_data["target_id"]

            # Allow speaker references (not in entity list) as sources
            if source_id not in entity_ids and source_id not in chunk.speaker_names:
                continue

            if target_id not in entity_ids:
                continue

            relationship = ChunkRelationship(
                source_id=source_id,
                target_id=target_id,
                relation_type=rel_data["relation_type"],
                sentiment=rel_data["sentiment"],
                evidence=rel_data["evidence"],
                evidence_sentence_index=rel_data["evidence_sentence_index"],
                confidence=rel_data.get("confidence", 0.5),
                chunk_index=chunk.chunk_index,
            )
            relationships.append(relationship)

        return relationships

    def _build_entity_extraction_prompt(
        self,
        chunk: TranscriptChunk,
        existing_entities: list[ChunkEntity] | None = None,
    ) -> str:
        """Build prompt for entity extraction from chunk."""
        # Format sentences
        sentences_text = "\n".join(
            f"[{i}] ({s.start_time}): {s.text}" for i, s in enumerate(chunk.sentences)
        )

        # Format existing entities for context
        existing_text = ""
        if existing_entities:
            existing_text = "\n\nEntities from previous context:\n"
            for entity in existing_entities[-10:]:  # Last 10 for brevity
                existing_text += f"- {entity.canonical_name} ({entity.entity_type})\n"

        prompt = f"""Extract ALL entities mentioned in this parliamentary transcript chunk.

Agenda Item: {chunk.agenda_item_title}
Speakers: {", ".join(chunk.speaker_names)}

Previous Context Summary:
{chunk.context_summary}

Sentences:
{sentences_text}
{existing_text}

Extract entities with:
1. **entity_id**: Unique slug (e.g., "bill_cybercrime_2024", "person_cummins")
2. **entity_type**: person, organization, place, law, concept, event, numeric_fact, policy_position
3. **name**: Name as mentioned in text
4. **canonical_name**: Standardized version
5. **aliases**: Alternative names/spelling variations
6. **description**: Brief description (1-2 sentences)
7. **mentions**: Where mentioned (sentence_index, context)
8. **confidence**: Extraction confidence (0-1)

Important:
- Include speaker names as "person" entities
- Capture laws, bills, organizations, places, concepts
- Note any numeric facts (amounts, dates, statistics)
- Record policy positions (stances on issues)
- Be thorough - extract ALL entities mentioned
"""

        return prompt

    def _build_relationship_extraction_prompt(
        self,
        chunk: TranscriptChunk,
        entities: list[ChunkEntity],
    ) -> str:
        """Build prompt for relationship extraction from chunk."""
        # Format sentences
        sentences_text = "\n".join(
            f"[{i}] ({s.start_time}): {s.text}" for i, s in enumerate(chunk.sentences)
        )

        # Format entity list
        entity_list_text = "\n".join(
            f"- {e.entity_id}: {e.canonical_name} ({e.entity_type})" for e in entities
        )

        # Format speakers
        speakers_text = "\n".join(f"- {name} (person)" for name in chunk.speaker_names)

        prompt = f"""Extract ALL relationships between entities in this parliamentary transcript chunk.

Agenda Item: {chunk.agenda_item_title}

Sentences:
{sentences_text}

Entities (use ONLY these IDs):
{entity_list_text}

Speakers (can be relationship sources):
{speakers_text}

For each relationship:
1. **source_id**: Entity or speaker ID making the statement/action
2. **target_id**: Entity ID being referenced/acted upon
3. **relation_type**: mentions, supports, opposes, relates_to, references, questions, answers, states
4. **sentiment**: positive, negative, or neutral
5. **evidence**: Direct quote from transcript
6. **evidence_sentence_index**: Which sentence [index] contains the evidence
7. **confidence**: Relationship confidence (0-1)

Guidelines:
- Use ONLY entity IDs and speaker names from the lists above
- Speakers can be sources (e.g., speaker "mentions" a bill)
- Look for: mentions, support/opposition, questions, statements of fact
- Include sentiment based on tone (e.g., "opposes" is negative)
- Be thorough - capture ALL relationships
"""

        return prompt

    def _generate_context_summary(self, chunk: TranscriptChunk) -> str:
        """Generate a brief summary of chunk content for context."""
        # Simple summary: mention speakers and key topics
        speakers_str = ", ".join(chunk.speaker_names)
        return f"Previous chunk ({chunk.agenda_item_title}) with speakers: {speakers_str}"

    def process_transcript(
        self,
        agenda_item_title: str,
        speech_blocks: list[SpeechBlock],
    ) -> tuple[list[ChunkEntity], list[ChunkRelationship]]:
        """
        Process entire transcript agenda item in chunks.

        Args:
            agenda_item_title: Title of agenda item
            speech_blocks: List of speech blocks

        Returns:
            Tuple of (all entities, all relationships)
        """
        chunks = self.create_chunks(agenda_item_title, speech_blocks)

        all_entities: list[ChunkEntity] = []
        all_relationships: list[ChunkRelationship] = []

        for chunk in chunks:
            entities, relationships = self.extract_from_chunk(chunk, all_entities)
            all_entities.extend(entities)
            all_relationships.extend(relationships)

        return all_entities, all_relationships
