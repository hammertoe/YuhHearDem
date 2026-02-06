# Quick Start Guide

This guide walks you through getting YuhHearDem running with real data.

**Related Documentation**:
- [README.md](./README.md) - Project overview
- [AGENTS.md](./AGENTS.md) - Comprehensive codebase guide with code map
- [scripts/README.md](./scripts/README.md) - Detailed script documentation
- [USAGE.md](./USAGE.md) - Usage examples

**Important**: This system processes YouTube videos by passing URLs directly to the Gemini API. Video files are never downloaded locally. See [AGENTS.md](./AGENTS.md) for details.

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

```bash
mkdir -p data/papers
```

### Option B: Automated

```bash
# Scrape session papers (optional, for context only)
python scripts/scrape_session_papers.py --download
```

**Note:** The scraper may need adjustments based on website structure. For now, video ingestion is primary focus.

## Step 3: Ingest Data

Once you have video URLs:

### Ingest Videos

First, create a mapping file `data/video_mapping.json`:
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
python scripts/ingest_video.py --mapping data/video_mapping.json
```

This will:
- Create/update Session records with stable IDs (`s_{sitting_number}_{YYYY_MM_DD}`)
- Create Video records linked to Sessions (`video_id = youtube_id`)
- Transcribe the video via Gemini API
- Create AgendaItem records for each agenda topic (`agenda_item_id = {session_id}_a{index}`)
- Create TranscriptSegment records with stable IDs (`segment_id = {youtube_id}_{start_time_seconds:05d}`)
- Extract entities and relationships
- Create RelationshipEvidence rows linking relationships to transcript segments

### Single Video Ingestion

```bash
python scripts/ingest_video.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --chamber house \
  --session-date "2024-01-15" \
  --sitting-number "10"
```

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

## What Each Step Does

### Video Ingestion
1. **Passes YouTube URL directly to Gemini Video API** (no download)
2. Transcribes with speaker attribution
3. Creates Session, Video, AgendaItem, Speaker, TranscriptSegment records
4. Extracts entities from transcript
5. Creates Entity, Relationship, RelationshipEvidence records
6. All IDs are stable and deterministic

### ID Formats
- Session ID: `s_{sitting_number}_{YYYY_MM_DD}` (e.g., `s_10_2026_01_15`)
- Video ID: YouTube ID (e.g., `abc123xyz`)
- Segment ID: `{youtube_id}_{start_time_seconds:05d}` (e.g., `abc123xyz_00005`)
- Agenda Item ID: `{session_id}_a{index}` (e.g., `s_10_2026_01_15_a0`)
- Speaker ID: `p_{last_name}_{initials}` (e.g., `p_smith_jd`)

## Next Steps

Once you have data ingested:

1. Add more session papers and videos
2. Run the daily pipeline for automation
3. Export or query the knowledge graph from scripts

For more details, see:
- `scripts/README.md` - Detailed script documentation
- `README.md` - Full project documentation

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](./README.md) | Project overview and quick start |
| [USAGE.md](./USAGE.md) | Usage examples |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide |
