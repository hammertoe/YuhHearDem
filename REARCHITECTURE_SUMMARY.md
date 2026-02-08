# Re-Architecture Implementation Summary

## Overview

This document summarizes the complete re-architecture of the YuhHearDem ingestion pipeline to address:
- Insufficient entity extraction
- Missing relationship provenance
- Lack of speaker deduplication
- Need for constrained decoding

## Changes Made

### Phase 1: Enhanced Speaker Model & Deduplication

**Files Modified:**
- `models/speaker.py` - Added `party`, `pronouns`, `session_ids` fields, updated field lengths

**Files Created:**
- `services/speaker_service.py` - Complete speaker management service with:
  - Three-stage matching (exact → fuzzy with role disambiguation → surname+role)
  - UUID-based canonical ID generation (collision-resistant)
  - Session tracking for speakers
  - Automatic alias merging

### Phase 2: JSON Schema Constraints for Structured Output

**Files Created:**
- `services/schemas.py` - Complete JSON schemas for constrained decoding:
  - `TRANSCRIPT_SCHEMA` - Structured transcript with timestamps
  - `ENTITY_SCHEMA` - Entity extraction with confidence scores
  - `RELATIONSHIP_SCHEMA` - Relationship extraction with evidence
  - `CHUNK_ENTITY_SCHEMA` - Chunk-specific entity extraction
  - `CHUNK_RELATIONSHIP_SCHEMA` - Chunk-specific relationship extraction
  - `DEDUPLICATION_SCHEMA` - LLM decision schema for entity merging

### Phase 3: Chunked Transcript Processing

**Files Created:**
- `services/chunked_processor.py` - Chunked processing service with:
  - 7-sentence chunks with 2-sentence overlap
  - Context preservation between chunks
  - Two-pass extraction per chunk (entities → relationships)
  - Mention tracking within chunks

**Supporting Files:**
- `services/transcript_models.py` - Structured transcript data models:
  - `TranscriptSentence` - With timestamp conversion
  - `TranscriptSpeechBlock` - Speaker + sentences
  - `TranscriptAgendaItem` - Topic + speech blocks
  - `StructuredTranscript` - Complete session transcript

### Phase 4: Global Entity Deduplication (Batch-Based)

**Files Modified:**
- `models/entity.py` - Added embedding vector field (768 dimensions for all-mpnet-base-v2), updated_at field

**Files Created:**
- `services/entity_deduplication.py` - Batch deduplication service with:
  - Hybrid matching (30% fuzzy + 70% vector similarity)
  - LLM ambiguity resolution
  - Entity merging with alias consolidation
  - Relationship ID remapping
  - Configurable thresholds (default: 85% fuzzy, 85% vector, 80% hybrid)

**Scripts Created:**
- `scripts/run_deduplication.py` - Standalone deduplication runner

### Phase 5: Relationship Extraction with Sentence-Level Provenance

**Files Modified:**
- `models/relationship.py` - Complete overhaul:
  - Added `evidence_quote` - Direct transcript quote
  - Added `evidence_timestamp` - XmYs format
  - Added `evidence_timestamp_seconds` - For sorting/filtering
  - Added hierarchical location fields (session_id, video_id, agenda_item_index, speech_block_index, sentence_index)
  - Added composite indexes for provenance queries
  - Added unique constraint on (source, target, relation, session)

### Phase 6: Mention Tracking Model

**Files Modified:**
- `models/__init__.py` - Added Mention model export

**Files Created:**
- `models/mention.py` - Comprehensive mention tracking:
  - Exact sentence-level location (session → agenda → speech → sentence)
  - Timestamp in XmYs format + seconds
  - Context (first 200 chars)
  - Speaker reference
  - Mention type (direct, alias, pronoun_reference)
  - Composite indexes for common queries

### Phase 7: Integration & New Ingestion Pipeline

**Files Created:**
- `services/unified_ingestion.py` - Complete unified pipeline:
  - Structured transcript extraction with constrained decoding
  - Speaker deduplication during ingestion
  - Chunked entity/relationship extraction
  - Automatic mention creation
  - Relationship provenance tracking

**Scripts Created:**
- `scripts/ingest_video_unified.py` - New ingestion script using unified pipeline
- `scripts/init_database.py` - Database initialization with new schema

## Usage

### 1. Initialize Database

```bash
python scripts/init_database.py
```

This creates all tables with the new schema including:
- pgvector extension for embeddings
- Updated speaker, entity, relationship, and mention tables
- Proper indexes for performance

### 2. Ingest a Video

```bash
python scripts/ingest_video_unified.py \
  --url "https://youtube.com/watch?v=VIDEO_ID" \
  --date 2024-01-15 \
  --chamber senate \
  --sitting 67 \
  --order-paper data/papers/order_paper_67.pdf \
  --fps 0.5
```

Options:
- `--url`: YouTube video URL (required)
- `--date`: Session date YYYY-MM-DD (required)
- `--chamber`: senate or house (required)
- `--sitting`: Sitting number (optional)
- `--order-paper`: Path to order paper PDF for speaker context (optional)
- `--fps`: Frames per second for video analysis (default: 0.5)

### 3. Run Entity Deduplication (Periodically)

```bash
python scripts/run_deduplication.py
```

This:
- Scans all entities for similarities
- Uses LLM to resolve ambiguous matches
- Merges duplicates
- Remaps relationship references

**Run this periodically, not after every ingestion.**

## Architecture Overview

```
YouTube Video
    ↓
Structured Transcript (JSON Schema Constrained)
    ↓
Speaker Deduplication (3-stage matching)
    ↓
Chunked Processing (7 sentences, 2 overlap)
    ├─→ Entity Extraction (per chunk)
    ├─→ Relationship Extraction (per chunk)
    └─→ Mention Tracking (per entity)
    ↓
Database Persistence
    ├─→ sessions
    ├─→ videos
    ├─→ speakers (deduplicated)
    ├─→ agenda_items
    ├─→ entities
    ├─→ relationships (with provenance)
    └─→ mentions (sentence-level)
    ↓
Periodic Deduplication (batch process)
    ├─→ Hybrid matching (fuzzy + vector)
    ├─→ LLM ambiguity resolution
    ├─→ Entity merging
    └─→ Relationship remapping
```

## Key Improvements

### 1. Constrained Decoding
- Gemini now outputs strict JSON via `response_schema`
- No more parsing errors or hallucinated fields
- Type-safe output with enums for entity/relation types

### 2. Speaker Deduplication
- Parliamentarians are first-class objects
- UUID-based canonical IDs prevent collisions
- Three-stage matching: exact → fuzzy + role → surname + role
- Tracks session appearances

### 3. Chunked Processing
- 7-sentence chunks with 2-sentence overlap
- Better entity coverage (not overwhelmed by long transcripts)
- Context preserved between chunks
- Two-pass extraction per chunk

### 4. Global Entity Deduplication
- Hybrid scoring: 30% fuzzy + 70% vector (all-mpnet-base-v2)
- LLM resolves ambiguous cases
- Batch processing (not on-the-fly)
- Merges aliases, descriptions, confidence scores

### 5. Sentence-Level Provenance
- Every relationship has:
  - Evidence quote from transcript
  - Exact timestamp (XmYs format)
  - Hierarchical location (agenda/speech/sentence index)
- Every mention has:
  - Exact sentence location
  - Timestamp + context
  - Speaker reference

## Environment Variables

Required:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/yuhheardem
GOOGLE_API_KEY=your_api_key_here
```

Optional:
```bash
FUZZY_MATCH_THRESHOLD=85  # Default fuzzy matching threshold
```

## Next Steps

1. **Test the pipeline** with a sample video
2. **Run deduplication** after ingesting a few sessions
3. **Monitor performance** - adjust chunk size if needed
4. **Query the knowledge graph** using the provenance fields
5. **Iterate** based on extraction quality

## Notes

- **No backwards compatibility** - this is a clean break
- **Database must be reinitialized** - run `init_database.py`
- **Deduplication is manual** - run periodically, not automatically
- **Embeddings use all-mpnet-base-v2** (768 dimensions)
