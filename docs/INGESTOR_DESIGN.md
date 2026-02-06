# Ingestor Design: Transcript + Knowledge Graph

This document describes a clean-slate schema and ingestion workflow for the YuhHearDem transcription generator and knowledge-graph extractor. It is written so another agent can update the ingestors to produce the required data for the prompt JSON format.

## Goals
- Stable, compact, human-readable IDs in the prompt JSON.
- Explicit evidence links between relationships and transcript segments.
- No heuristic matching at runtime; all links written during ingestion.
- Support multiple evidence segments per relationship.

## Database Schema (Clean-Slate)

### sessions
- `session_id` (PK, text) — e.g., `s_125_2026_01_06`
- `date` (date)
- `title` (text)
- `sitting_number` (text)
- `chamber` (text)
- `created_at` (timestamp)

### videos
- `video_id` (PK, text) — use YouTube ID directly
- `session_id` (FK → sessions.session_id)
- `platform` (text, default `youtube`)
- `url` (text)
- `duration_seconds` (int)
- `created_at` (timestamp)

### speakers
- `speaker_id` (PK, text) — e.g., `p_bradshaw`
- `name` (text, canonical full)
- `title` (text)
- `role` (text)
- `chamber` (text)
- `aliases` (jsonb)
- `created_at` (timestamp)

### transcript_segments
- `segment_id` (PK, text) — e.g., `{youtube_id}_{start_time_seconds:05d}`
- `session_id` (FK → sessions.session_id)
- `video_id` (FK → videos.video_id)
- `speaker_id` (FK → speakers.speaker_id)
- `start_time_seconds` (int)
- `end_time_seconds` (int)
- `text` (text)
- `agenda_item_id` (FK, optional)
- `speech_block_index` (int)
- `segment_index` (int)
- `embedding` (vector, optional)
- `embedding_model` (text)
- `created_at` (timestamp)

### entities
- `entity_id` (PK, text) — e.g., `bill_road_traffic_2025`
- `name` (text)
- `canonical_name` (text)
- `entity_type` (text) — Person, Law, System, Org, etc.
- `entity_subtype` (text)
- `description` (text)
- `aliases` (jsonb)
- `created_at` (timestamp)

### relationships
- `relationship_id` (PK, text or UUID)
- `source_entity_id` (FK → entities.entity_id)
- `target_entity_id` (FK → entities.entity_id)
- `relation` (text) — e.g., AMENDS / ADVOCATES_FOR
- `description` (text)
- `confidence` (float)
- `created_at` (timestamp)

### relationship_evidence
- `evidence_id` (PK, UUID)
- `relationship_id` (FK → relationships.relationship_id)
- `segment_id` (FK → transcript_segments.segment_id)
- `video_id` (FK → videos.video_id)
- `start_time_seconds` (int)
- `created_at` (timestamp)

Indexes:
- `relationship_evidence (relationship_id)`
- `relationship_evidence (segment_id)`
- `relationship_evidence (video_id, start_time_seconds)`

## Prompt JSON Format
The LLM prompt should contain a compact reified JSON object:

```json
{
  "sessions": {
    "s_125_2026_01_06": {
      "date": "2026-01-06",
      "title": "HOUSE OF ASSEMBLY | 125th SITTING",
      "video_url": "https://youtu.be/Syxyah7QIaM"
    }
  },
  "entities": {
    "bill_road_traffic_2025": {"name": "Road Traffic (Amendment) Bill 2025", "type": "Legislation"}
  },
  "transcript_segments": {
    "Syxyah7QIaM_00395": {
      "session_id": "s_125_2026_01_06",
      "speaker_id": "p_bradshaw",
      "start_time": 395,
      "text": "We also have accompanying the Road Traffic Act..."
    }
  },
  "relationships": [
    {
      "source": "bill_road_traffic_2025",
      "target": "act_295",
      "relation": "AMENDS",
      "description": "Updates safety regulations",
      "evidence_segment_ids": ["Syxyah7QIaM_00395"]
    }
  ]
}
```

## Transcription Generator Responsibilities
- Create or update `sessions` based on session metadata.
- Create or update `videos` with `video_id = youtube_id`.
- Normalize speakers and create `speaker_id` (stable slug).
- Write `transcript_segments` with stable `segment_id`:
  - `segment_id = {youtube_id}_{start_time_seconds:05d}`
- Store embeddings and model metadata.

### ID Generation Guidance
- `session_id`: `s_{sitting_number}_{YYYY_MM_DD}`
- `video_id`: `{youtube_id}`
- `segment_id`: `{youtube_id}_{start_time_seconds:05d}`
- `speaker_id`: `p_{last}_{initials}` (or a curated registry id)
- `entity_id`: normalized slug of entity name or source id

## Knowledge Graph Extractor Responsibilities
- Extract entities and write `entities` with stable `entity_id`.
- Extract relationships and write `relationships`.
- For each relationship, insert one or more `relationship_evidence` rows that point to the exact `segment_id` used to infer the relation.
- Always populate `video_id` and `start_time_seconds` in `relationship_evidence` for direct citation.

## Rationale for Explicit Evidence
- Eliminates heuristic evidence matching at runtime.
- Allows multiple segments to support a single relationship.
- Keeps prompt JSON small while precise.

## Migration Strategy (if adopting from current schema)
1. Add new columns/tables while keeping existing UUIDs.
2. Backfill stable IDs using deterministic rules above.
3. Update ingestors to always write stable IDs going forward.
4. Update prompt builder to prefer stable IDs, with fallback to UUIDs for any legacy rows.
