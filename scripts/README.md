# Ingestion Scripts

Complete pipeline for scraping and ingesting Barbados parliamentary data.

**Related Documentation**:
- [AGENTS.md](../AGENTS.md) - Comprehensive codebase guide with code map
- [README.md](../README.md) - Project overview and quick start
- [QUICKSTART.md](../QUICKSTART.md) - Step-by-step local setup
- [USAGE.md](../USAGE.md) - Usage examples

**Important**: This system processes YouTube videos by passing URLs directly to Gemini API. Video files are never downloaded locally. See [AGENTS.md](../AGENTS.md) for details.

## Prerequisites

Environment variables must be set in `.env`:
```bash
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/yuhheardem
```

## Quick Start

### 1. Ingest Videos (Primary Workflow)

Video ingestion now handles session creation, agenda items, transcription, and knowledge graph extraction:

```bash
# Single video URL (YouTube URL passed directly to Gemini - no download)
python scripts/ingest_video.py \
    --url https://www.youtube.com/watch?v=VIDEO_ID \
    --chamber house \
    --session-date "2024-01-15" \
    --sitting-number "10"

# From mapping file
python scripts/ingest_video.py --mapping data/video_mapping.json
```

### 2. Scrape Session Papers (Optional, for context only)

```bash
# List available papers
python scripts/scrape_session_papers.py

# Download PDFs
python scripts/scrape_session_papers.py --download

# Specific chamber
python scripts/scrape_session_papers.py --chamber senate --download
```

## New Schema Overview

The database schema has been completely redesigned to use stable, compact IDs:

### Tables

- **sessions**: Parliamentary sessions (`session_id` = `s_{sitting_number}_{YYYY_MM_DD}`)
- **videos**: Video recordings (`video_id` = YouTube ID)
- **speakers**: Canonical speaker database (`speaker_id` = `p_{last_name}_{initials}`)
- **agenda_items**: Agenda topics from order papers (`agenda_item_id` = `{session_id}_a{index}`)
- **transcript_segments**: Transcribed segments (`segment_id` = `{youtube_id}_{start_time_seconds:05d}`)
- **entities**: Knowledge graph entities (`entity_id` = stable slug or source ID)
- **relationships**: Entity relationships (`relationship_id` = UUID)
- **relationship_evidence**: Evidence links (`evidence_id` = UUID)

### Evidence Links

Relationship evidence is now explicit - no heuristic matching at runtime. Each relationship links to specific transcript segments via `relationship_evidence` table.

## Script Details

### `ingest_video.py`

Primary ingestion script that creates the complete knowledge graph.

**Features:**
- Creates Session and Video records with stable IDs
- Transcribes with speaker attribution using Gemini Video API
- Creates AgendaItem records for each agenda topic
- Creates TranscriptSegment records with stable IDs
- Extracts entities and relationships
- Creates RelationshipEvidence rows linking relationships to segments
- Stores embeddings and model metadata
- Skips already ingested videos

**Options:**
- `--url`: YouTube URL to ingest
- `--mapping`: JSON file with video metadata
- `--chamber`: house or senate (default: house)
- `--session-date`: Session date (YYYY-MM-DD)
- `--sitting-number`: Sitting number
- `--session-id`: Stable session ID (auto-generated if not provided)
- `--fps`: Frames per second for video sampling

**Video Mapping Format:**
```json
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "chamber": "house",
        "session_date": "2024-01-15",
        "session_id": "s_10_2024_01_15",
        "sitting_number": "10"
    }
]
```

### `scrape_session_papers.py`

Scraps session papers from parliament website.

**Note:** This script is optional and primarily used for reference. Video ingestion works independently.

**Options:**
- `--chamber`: house or senate (default: house)
- `--download`: Download PDFs to data directory

### `reset_db.py`

Database reset utility for development.

Drops all tables and recreates from SQLAlchemy models.

```bash
python scripts/reset_db.py
```

## Workflow

### Complete Workflow

1. **Get video URLs:**
   - Go to Barbados Parliament YouTube channel
   - Copy video URLs

2. **Create video mapping:**
   - Create `data/video_mapping.json` with metadata

3. **Ingest videos:**
   - Run video ingestion script
   - Stable IDs auto-generated from metadata

## Schema Changes

### Removed (Old Schema)
- `order_papers` table
- `mentions` table (replaced by `relationship_evidence`)
- `messages` table (moved to UI package)
- `community_*` tables (moved to UI package)
- GraphRAG-specific tables (moved to UI package)

### Added (New Schema)
- `agenda_items` table (links sessions to transcript segments)
- `relationship_evidence` table (explicit evidence links)
- Stable text primary keys on all major tables
- Embedding support on `transcript_segments`

## ID Formats

All IDs are deterministic and stable:

- `session_id`: `s_{sitting_number}_{YYYY_MM_DD}`
- `video_id`: YouTube ID (e.g., `abc123xyz`)
- `segment_id`: `{youtube_id}_{start_time_seconds:05d}` (e.g., `abc123xyz_00005`)
- `agenda_item_id`: `{session_id}_a{index}` (e.g., `s_10_2026_01_15_a0`)
- `speaker_id`: `p_{last_name}_{initials}` (e.g., `p_smith_jd`)
- `entity_id`: Stable slug from source or provided (e.g., `bill_road_traffic_2025`)

## Troubleshooting

### Gemini API Issues

If transcription/parsing fails:
1. Check API key in `.env`
2. Verify quota and billing
3. Check network connectivity to Google API
4. Reduce FPS if hitting token limits

### Database Issues

If ingestion fails:
1. Ensure PostgreSQL is running: `docker-compose up`
2. Check database URL in `.env`
3. Reset schema: `python scripts/reset_db.py`
4. Check logs for detailed error messages

## Next Steps

After ingestion:

1. Add more videos to mapping file
2. Run video ingestion script
3. Query knowledge graph via UI package

For more details, see:
- `INGESTOR_DESIGN.md` - Complete schema design and ingestion flow
- `README.md` - Full project documentation

---

## Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [AGENTS.md](../AGENTS.md) | Codebase guide with code map | AI agents, developers |
| [README.md](../README.md) | Project overview and quick start | Everyone |
| [QUICKSTART.md](../QUICKSTART.md) | Step-by-step local setup | New users |
| [USAGE.md](../USAGE.md) | Usage examples | Users |
| [scripts/README.md](./README.md) | Data ingestion scripts guide | Users |
