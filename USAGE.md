# YuhHearDem - Usage Summary

## What Was Created

Complete data ingestion pipeline with the following scripts:

### Primary Scripts
- `ingest_video.py` - Transcribes videos (using YouTube URLs directly) & saves to database
- `scrape_session_papers.py` - Scrapes session papers from parliament website
- `reset_db.py` - Database reset utility for development

### Documentation
- `scripts/README.md` - Detailed script documentation
- `QUICKSTART.md` - Step-by-step getting started guide
- `docs/INGESTOR_DESIGN.md` - Schema design and data flow

**Important**: This system processes YouTube videos by passing URLs directly to Gemini API. Video files are never downloaded locally. See [AGENTS.md](./AGENTS.md) for details.

## How to Use

### Option 1: Quick Start (Recommended)

**Step 1: Get YouTube Video URL**

Go to Barbados Parliament YouTube channel and copy a video URL.

**Step 2: Ingest to Database**

```bash
# Simplest approach - auto-detects metadata
python scripts/ingest_video.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --no-thinking
```

**What happens:**
1. Video metadata is auto-detected (session date, chamber, sitting number)
2. YouTube URL is passed directly to Gemini Video API (no download)
3. Video is transcribed with speaker attribution
4. Knowledge graph is extracted (entities and relationships)
5. Data is saved to PostgreSQL with stable IDs

### Option 2: Batch Ingestion

Create a mapping file `data/video_mapping.json`:

```json
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=ABC123",
        "chamber": "house",
        "session_date": "2024-01-15"
    },
    {
        "youtube_url": "https://www.youtube.com/watch?v=DEF456",
        "chamber": "house",
        "session_date": "2024-02-20"
    }
]
```

Then ingest:

```bash
python scripts/ingest_video.py --mapping data/video_mapping.json --no-thinking
```

### Option 3: Scrape Session Papers (Optional)

```bash
# List available papers
python scripts/scrape_session_papers.py

# Download PDFs
python scripts/scrape_session_papers.py --download

# Specific chamber
python scripts/scrape_session_papers.py --chamber senate --download
```

**Note:** The scraper is a template and may need manual adjustment. Manual download of PDFs is often faster and more reliable.

## Command-Line Options

### `ingest_video.py`

```bash
python scripts/ingest_video.py [OPTIONS]

Options:
  --url URL                 # YouTube URL to ingest
  --mapping PATH             # JSON file with video metadata
  --chamber {house,senate}  # Chamber (default: house)
  --session-date YYYY-MM-DD   # Session date
  --sitting-number N        # Sitting number
  --session-id ID           # Stable session ID (auto-generated if not provided)
  --fps N                   # Frames per second for video sampling
  --start-time N            # Start time in seconds
  --end-time N              # End time in seconds
  --no-thinking              # Disable Gemini thinking mode (faster, recommended)
```

### `scrape_session_papers.py`

```bash
python scripts/scrape_session_papers.py [OPTIONS]

Options:
  --chamber {house,senate}  # Chamber (default: house)
  --download                  # Download PDFs to data directory
```

### `reset_db.py`

```bash
python scripts/reset_db.py

# Drops all tables and recreates from SQLAlchemy models
# WARNING: This will delete all data!
# Development only
```

## What Each Script Does

### `ingest_video.py`

Primary ingestion script that creates the complete knowledge graph.

**Features:**
- Auto-detects session date, chamber, and sitting number from video metadata
- Multi-method metadata extraction (Invidious, Piped, oEmbed, RSS, YouTube watch page)
- Creates Session and Video records with stable IDs
- Transcribes video via Gemini Video API (no download)
- Creates AgendaItem records for each agenda topic
- Creates TranscriptSegment records with stable IDs
- Handles missing timecodes with counter suffixes to prevent duplicate IDs
- Extracts entities from transcript
- Creates Entity, Relationship, and RelationshipEvidence records
- Stores embeddings and model metadata
- Skips already ingested videos
- Automatically deletes and replaces existing segments on re-ingestion

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

- Extracts PDF links, titles, and dates
- Downloads PDFs to `data/papers/`
- Note: This is optional and primarily for reference. Video ingestion works independently.

### `reset_db.py`

Database reset utility for development.

- Drops all tables
- Recreates from SQLAlchemy models
- Warning: This will delete all data!

## ID Formats

All IDs are stable and deterministic:

| Entity | Format | Example |
|--------|---------|----------|
| Session ID | `s_{sitting_number}_{YYYY_MM_DD}` | `s_10_2026_01_15` |
| Video ID | YouTube ID | `Syxyah7QIaM` |
| Segment ID | `{youtube_id}_{start_time_seconds:05d}` | `abc123xyz_00395` |
| - With timecode missing | `{youtube_id}_{start_time_seconds:05d}_c{counter}` | `abc123xyz_00000_c01` |
| Agenda Item ID | `{session_id}_a{index}` | `s_10_2026_01_15_a0` |
| Speaker ID | `p_{last_name}_{initials}` | `p_smith_jd` |
| Entity ID | Stable slug from source | `bill_road_traffic_2025` |

## Troubleshooting

### Module Not Found Errors

Make sure you activate the virtual environment:
```bash
source venv/bin/activate
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart if needed
docker-compose restart
```

### Gemini API Issues

- Check `.env` file has `GOOGLE_API_KEY`
- Verify API key has billing enabled
- Check Google Cloud console for quota usage
- API has rate limits - use `--no-thinking` for faster processing
- Start with smaller batches

### Duplicate Key Errors

If you see duplicate key errors during re-ingestion:
1. Run the ingestion again - segments are automatically cleaned up
2. If persistent, use `reset_db.py` to clear the database (development only)

## Current Status

✅ Scripts created and committed
✅ Documentation written
✅ Type errors fixed
✅ Video download code removed - URLs processed directly by Gemini
✅ Auto-detection of session metadata
✅ Multi-method metadata extraction with fallbacks
✅ `--no-thinking` flag for faster processing
✅ Automatic handling of duplicate segment IDs

## Notes

- The scraper is a template and may need adjustment for website changes
- Manual download of PDFs is often faster and more reliable
- Start with 1-2 test videos to verify the pipeline works
- Gemini API has rate limits - use `--no-thinking` for faster processing
- Check quota if requests fail
- All changes are committed to git
- **Videos are never downloaded** - YouTube URLs processed directly by Gemini API

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](./README.md) | Project overview and quick start |
| [QUICKSTART.md](./QUICKSTART.md) | Step-by-step local setup |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide |
| [docs/INGESTOR_DESIGN.md](./docs/INGESTOR_DESIGN.md) | Schema design and data flow |
