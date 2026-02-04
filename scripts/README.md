# Ingestion Scripts

Complete pipeline for scraping, parsing, and ingesting Barbados parliamentary data.

**Related Documentation**:
- [AGENTS.md](../AGENTS.md) - Comprehensive codebase guide with code map
- [README.md](../README.md) - Project overview and quick start
- [QUICKSTART.md](../QUICKSTART.md) - Step-by-step local setup
- [USAGE.md](../USAGE.md) - Usage examples

**Important**: This system processes YouTube videos by passing URLs directly to the Gemini API. Video files are never downloaded locally. See [AGENTS.md](../AGENTS.md) for details.

## Prerequisites

Environment variables must be set in `.env`:
```bash
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/yuhheardem
```

## Quick Start

### 1. Run Daily Pipeline (Recommended)

Automated daily pipeline that scrapes papers, monitors YouTube, matches videos, and transcribes:

```bash
# Run full daily pipeline (no video download needed)
python scripts/daily_pipeline.py

# Run specific steps
python scripts/daily_pipeline.py --step scrape
python scripts/daily_pipeline.py --step match
```

### 2. Run Full Ingestion Pipeline

Scrapes session papers, downloads them, parses with Gemini, and saves to database:

```bash
# Scrape and ingest order papers
python scripts/run_full_ingestion.py

# With specific chamber and limit
python scripts/run_full_ingestion.py --chamber house --max-papers 10
```

### 3. Individual Steps

#### Scrape Session Papers

```bash
# List available papers
python scripts/scrape_session_papers.py

# Download PDFs
python scripts/scrape_session_papers.py --download

# Specific chamber
python scripts/scrape_session_papers.py --chamber senate --download
```

#### Ingest Order Papers

```bash
# Single PDF
python scripts/ingest_order_paper.py data/papers/session_paper.pdf

# All PDFs in directory
python scripts/ingest_order_paper.py data/papers/

# With associated YouTube video
python scripts/ingest_order_paper.py data/papers/paper.pdf --video-id VIDEO_ID
```

#### Ingest Videos

```bash
# Single video URL (YouTube URL passed directly to Gemini - no download)
python scripts/ingest_video.py \
    --url https://www.youtube.com/watch?v=VIDEO_ID \
    --session-date 2024-01-15 \
    --chamber house

# From mapping file
python scripts/ingest_video.py --mapping data/video_ingest_mapping.json

# With order paper context (better transcription accuracy)
python scripts/ingest_video.py \
    --url https://www.youtube.com/watch?v=VIDEO_ID \
    --order-paper data/papers/session_paper.pdf
```

#### Match Videos to Papers

```bash
# Match all unprocessed videos
python scripts/match_videos_to_papers.py

# Show only ambiguous matches for manual review
python scripts/match_videos_to_papers.py --review-only

# Interactive review mode
python scripts/match_videos_to_papers.py --interactive
```

## Workflow

### Complete Workflow

1. **Create directories:**
   ```bash
   mkdir -p data/papers
   ```

2. **Run full pipeline:**
   ```bash
   python scripts/run_full_ingestion.py --chamber house --max-papers 10
   ```

3. **Monitor and match videos:**
   ```bash
   python scripts/daily_pipeline.py --step monitor
   python scripts/daily_pipeline.py --step match
   ```

### Manual Workflow

For more control, run steps individually:

1. **Scrape session papers:**
   ```bash
   python scripts/scrape_session_papers.py --download --output data/papers
   ```

2. **Ingest order papers:**
   ```bash
   python scripts/ingest_order_paper.py data/papers/
   ```

3. **Create video mapping** (matches PDFs to videos):
   Create `data/video_ingest_mapping.json`:
   ```json
   [
       {
           "youtube_url": "https://www.youtube.com/watch?v=ABC123",
           "chamber": "house",
           "session_date": "2024-01-15",
           "order_paper_pdf": "data/papers/session_paper.pdf"
       }
   ]
   ```

4. **Ingest videos (URLs processed directly by Gemini):**
   ```bash
   python scripts/ingest_video.py --mapping data/video_ingest_mapping.json
   ```

## Script Details

### `run_full_ingestion.py`

Orchestrates complete pipeline for order papers.

**Options:**
- `--chamber`: house or senate (default: house)
- `--max-papers`: Max order papers to scrape
- `--output`: Output directory (default: data/)

### `daily_pipeline.py`

Automated daily pipeline for complete workflow.

**Steps:**
1. `scrape` - Scrape new order papers
2. `monitor` - Check YouTube for new videos
3. `match` - Match videos to order papers
4. `process` - Transcribe matched videos (using URLs, no download)

### `scrape_session_papers.py`

Scrapes session papers from parliament website.

**Note:** You may need to adjust URL patterns and selectors based on actual website structure. The current implementation is a template.

### `ingest_order_paper.py`

Parses PDFs with Gemini Vision and saves to database.

**Features:**
- Extracts speakers and agenda items
- Creates video records if YouTube ID provided
- Syncs speakers to database
- Skips already ingested papers (by hash)

### `ingest_video.py`

Transcribes videos with Gemini and saves to database.

**Features:**
- Transcribes with speaker attribution
- Extracts entities from transcript
- Can use order paper for context
- Skips already ingested videos
- **Uses YouTube URLs directly** - no video download required

### `match_videos_to_papers.py`

Matches YouTube videos to order papers automatically.

**Options:**
- `--threshold`: Confidence threshold for auto-accept (default: 90)
- `--review-only`: Only show ambiguous matches
- `--interactive`: Run interactive review mode
- `--dry-run`: Show what would be matched without changes

## Troubleshooting

### Scraper Issues

If session papers don't scrape:
1. Check parliament website is accessible
2. Inspect HTML structure and update selectors in `scrape_session_papers.py`
3. Download PDFs manually if needed

### Gemini API Issues

If transcription/parsing fails:
1. Check API key in `.env`
2. Verify quota and billing
3. Check network connectivity to Google API
4. Reduce chunk size if hitting token limits

### Database Issues

If ingestion fails:
1. Ensure PostgreSQL is running: `docker-compose up`
2. Check database URL in `.env`
3. Run migrations: `alembic upgrade head`
4. Check logs for detailed error messages

## Next Steps

After ingestion:

1. **Start the API:**
   ```bash
   uvicorn app.main:app --reload
   ```

2. **Access the chat interface:**
   - Open browser to `http://localhost:8000`
   - Use `/chat` for the chat interface
   - Use `/graph` for the knowledge graph visualization

3. **Query the system:**
   - Ask about legislation, speakers, sessions
   - View entity relationships in the graph
   - Search transcripts semantically

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](../AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](../README.md) | Project overview and quick start |
| [QUICKSTART.md](../QUICKSTART.md) | Step-by-step local setup |
| [USAGE.md](../USAGE.md) | Usage examples |
| [ARCHITECTURE_ANALYSIS.md](../docs/ARCHITECTURE_ANALYSIS.md) | System architecture |
| [deployment.md](../docs/deployment.md) | Deployment guide |
