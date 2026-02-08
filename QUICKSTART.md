# Quick Start Guide

This guide walks you through getting YuhHearDem running with real data.

**Related Documentation**:
- [README.md](./README.md) - Project overview
- [AGENTS.md](./AGENTS.md) - Comprehensive codebase guide with code map
- [scripts/README.md](./scripts/README.md) - Detailed script documentation
- [USAGE.md](./USAGE.md) - Usage examples

**Important**: This system processes YouTube videos by passing URLs directly to Gemini API. Video files are never downloaded locally. See [AGENTS.md](./AGENTS.md) for details.

## Step 1: Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY and DATABASE_URL

# Start PostgreSQL
docker-compose up -d

# Initialize schema
python -c "import asyncio; from core.database import init_db; asyncio.run(init_db())"
```

## Step 2: Get Data

### Option A: Manual (Recommended for getting started)

1. **Get YouTube video URLs:**
   - Go to Barbados Parliament YouTube channel
   - Copy video URLs (these will be processed directly by Gemini - no download needed)

2. **Create data directory:**
```bash
mkdir -p data/papers
```

### Option B: Automated (Optional)

```bash
# Scrape session papers (optional, for context only)
python scripts/scrape_session_papers.py --download
```

**Note:** The scraper may need adjustments based on website structure. For now, video ingestion is the primary focus.

## Step 3: Ingest Data

Once you have video URLs:

### Ingest Videos

#### Single Video Ingestion (Simplest)

```bash
python scripts/ingest_video_unified.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --chamber house
```

**Auto-detection**: The script will automatically extract session date, chamber, and sitting number from the video metadata.

#### Single Video with Custom Metadata

```bash
python scripts/ingest_video_unified.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --chamber house \
  --session-date "2024-01-15" \
  --sitting-number "10"
```

#### From Mapping File

Create a mapping file `data/video_mapping.json`:
```json
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "chamber": "house",
        "session_date": "2024-01-15",
        "session_id": "s_10_2024_01_15"
    }
]
```

Then ingest (YouTube URL processed directly by Gemini - no download needed):
```bash
python scripts/ingest_video_unified.py --mapping data/video_mapping.json
```

#### Optional Flags

- `--no-thinking`: Disable Gemini thinking mode for faster processing (recommended)
- `--fps N`: Set frames per second for video sampling (default varies by model)
- `--start-time N`: Start processing at N seconds
- `--end-time N`: Stop processing at N seconds

### What Happens During Ingestion

1. **Metadata Extraction** (multi-method fallback):
   - Tries Invidious instance
   - Tries Piped instance
   - Tries YouTube oEmbed API
   - Tries RSS feeds
   - Falls back to YouTube watch page

2. **Video Transcription**:
   - YouTube URL passed directly to Gemini Video API (no download)
   - Transcribes with speaker attribution
   - Extracts agenda items from transcript

3. **Knowledge Graph Extraction**:
   - Pass 1: Extract entities (people, bills, laws, etc.)
   - Pass 2: Extract relationships between entities
   - Links relationships to specific transcript segments

4. **Database Persistence**:
   - Creates Session record with stable ID (`s_{sitting_number}_{YYYY_MM_DD}`)
   - Creates Video record linked to Session (`video_id = youtube_id`)
   - Creates AgendaItem records for each topic (`agenda_item_id = {session_id}_a{index}`)
   - Creates Speaker records with stable IDs (`speaker_id = p_{name}`)
   - Creates TranscriptSegment records with embeddings
   - Creates Entity records
   - Creates Relationship and RelationshipEvidence records

## ID Formats

All IDs are stable and deterministic:

- **Session ID**: `s_{sitting_number}_{YYYY_MM_DD}` (e.g., `s_10_2026_01_15`)
- **Video ID**: YouTube ID (e.g., `Syxyah7QIaM`)
- **Segment ID**: `{youtube_id}_{start_time_seconds:05d}` (e.g., `abc123xyz_00395`)
  - Note: If timecodes are missing, adds counter suffix (`_c01`, `_c02`) to prevent duplicates
- **Agenda Item ID**: `{session_id}_a{index}` (e.g., `s_10_2026_01_15_a0`)
- **Speaker ID**: `p_{last_name}_{initials}` (e.g., `p_smith_jd`)
- **Entity ID**: Stable slug (e.g., `bill_road_traffic_2025`)

## Troubleshooting

### "Module not found" errors

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
```

### Scraper doesn't find papers

The scraper is a template. You may need to:
1. Check actual parliament website structure
2. Or manually download PDFs (often faster)
3. The manual approach is recommended

### Database connection failed

```bash
# Check PostgreSQL is running
docker-compose ps

# Restart if needed
docker-compose restart

# Check logs
docker-compose logs postgres
```

### Gemini API issues

- Check API key in `.env`
- Verify quota and billing
- Start with smaller files first
- Check logs for specific error messages
- Use `--no-thinking` flag for faster processing

### Duplicate key errors during re-ingestion

The system automatically handles re-ingestion:
- Existing videos are skipped
- Existing segments are deleted and replaced
- If you see duplicate key errors, run the ingestion again (segments will be cleaned up)

## Next Steps

Once you have data ingested:

1. Add more session papers and videos
2. Run the daily pipeline for automation
3. Export or query the knowledge graph
4. Use the UI package for searching and visualization

For more details, see:
- `scripts/README.md` - Detailed script documentation
- `README.md` - Full project documentation
- `docs/INGESTOR_DESIGN.md` - Schema design and data flow

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](./README.md) | Project overview and quick start |
| [USAGE.md](./USAGE.md) | Usage examples |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide |
| [docs/INGESTOR_DESIGN.md](./docs/INGESTOR_DESIGN.md) | Schema design and data flow |
