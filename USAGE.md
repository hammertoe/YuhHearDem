# YuhHearDem - Usage Summary

## What Was Created

Complete data ingestion pipeline with the following scripts:

### Scripts
- `scrape_session_papers.py` - Scrapes session papers from parliament website
- `ingest_order_paper.py` - Parses PDFs & saves to database
- `ingest_video.py` - Transcribes videos (using YouTube URLs directly) & saves to database
- `match_videos_to_papers.py` - Matches videos to order papers automatically
- `run_full_ingestion.py` - Orchestrates full pipeline
- `daily_pipeline.py` - Automated daily pipeline

### Documentation
- `scripts/README.md` - Detailed script documentation
- `QUICKSTART.md` - Step-by-step getting started guide

**Important**: This system processes YouTube videos by passing URLs directly to the Gemini API. Video files are never downloaded locally. See [AGENTS.md](../AGENTS.md) for details.

## How to Use

### Option 1: Quick Start (Recommended)

**Step 1: Download Session Papers**
```bash
# Go to: https://www.barbadosparliament.com/order_papers/search
# Click "House of Assembly" tab
# Download PDFs to: data/papers/
```

**Step 2: Ingest to Database**
```bash
# Ingest order papers
python scripts/ingest_order_paper.py data/papers/

# Create mapping file for videos
# Create: data/video_mapping.json
# Format: See below

# Ingest videos (YouTube URLs processed directly by Gemini)
python scripts/ingest_video.py --mapping data/video_mapping.json
```

**Step 3: Start Application**
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

**Access Interface:**
- Chat: http://localhost:8000/static/chat.html
- Graph: http://localhost:8000/static/graph.html
- API Docs: http://localhost:8000/docs

### Option 2: Daily Pipeline (Recommended for Automation)

```bash
# Run full automated pipeline
python scripts/daily_pipeline.py

# Or run specific steps
python scripts/daily_pipeline.py --step scrape
python scripts/daily_pipeline.py --step match
python scripts/daily_pipeline.py --step process
```

### Option 3: Full Pipeline (Advanced)

```bash
# Run full ingestion pipeline for order papers
python scripts/run_full_ingestion.py --chamber house --max-papers 10

# Then match and process videos
python scripts/daily_pipeline.py --step match
```

Note: The scraper may need manual adjustment based on website structure. Manual download is often more reliable.

## File Format

### data/video_mapping.json

```json
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=ABC123",
        "chamber": "house",
        "session_date": "2024-01-15",
        "order_paper_pdf": "data/papers/session_paper.pdf"
    },
    {
        "youtube_url": "https://www.youtube.com/watch?v=DEF456",
        "chamber": "house",
        "session_date": "2024-02-20",
        "order_paper_pdf": "data/papers/session_paper_2.pdf"
    }
]
```

## What Each Script Does

### 1. scrape_session_papers.py

- Scrapes https://www.barbadosparliament.com/order_papers/search
- Extracts PDF links, titles, and dates
- Downloads PDFs to `data/papers/`
- Usage: `python scripts/scrape_session_papers.py --download`

### 2. ingest_order_paper.py

- Parses PDF with Gemini Vision API
- Extracts: session title, date, speakers, agenda items
- Saves to `order_papers` table
- Creates speaker records
- Usage: `python scripts/ingest_order_paper.py PDF_PATH`

### 3. ingest_video.py

- Transcribes YouTube video with Gemini API
- **Uses YouTube URLs directly** - no video download required
- Extracts entities from transcript
- Saves to `videos` table
- Links to order papers if provided
- Usage: `python scripts/ingest_video.py --mapping MAPPING_FILE`

### 4. match_videos_to_papers.py

- Matches YouTube videos to order papers automatically
- Based on session date, chamber, and sitting number
- Auto-accepts high-confidence matches
- Flags ambiguous matches for review
- Usage: `python scripts/match_videos_to_papers.py`

## Troubleshooting

### Module Not Found Errors

Make sure to activate the virtual environment:
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
- API has rate limits, start with small batches

## Current Status

✅ Scripts created and committed
✅ Documentation written
✅ Type errors fixed
✅ Scraper URL updated to correct parliament website
✅ Video download code removed - URLs processed directly by Gemini

## Next Steps

1. Download sample PDF from parliament website
2. Test ingestion with single files first
3. Start exploring via chat interface
4. Check knowledge graph visualization

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | Comprehensive codebase guide with code map |
| [README.md](./README.md) | Project overview and quick start |
| [QUICKSTART.md](./QUICKSTART.md) | Step-by-step local setup |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide |
| [ARCHITECTURE_ANALYSIS.md](./docs/ARCHITECTURE_ANALYSIS.md) | System architecture |
| [deployment.md](./docs/deployment.md) | Deployment guide |

## Example Workflow

```bash
# Create directories
mkdir -p data/papers

# 1. Download a session paper manually
# Visit: https://www.barbadosparliament.com/order_papers/search
# Save PDF to: data/papers/test.pdf

# 2. Ingest it
source venv/bin/activate
python scripts/ingest_order_paper.py data/papers/test.pdf

# 3. Create minimal mapping for video
# YouTube URL will be processed directly by Gemini - no download needed
cat > data/video_mapping.json << 'EOF'
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=SAMPLE",
        "chamber": "house",
        "session_date": "2024-01-15"
    }
]
EOF

# 4. Ingest video (URL passed directly to Gemini)
python scripts/ingest_video.py --mapping data/video_mapping.json

# 5. Start app
uvicorn app.main:app --reload

# 6. Open browser to: http://localhost:8000/static/chat.html
# 7. Ask: "What topics were in the session?"
```

## Notes

- The scraper is a template and may need adjustment for website changes
- Manual download of PDFs is often faster and more reliable
- Start with 1-2 test files to verify pipeline works
- Gemini API has rate limits - check quota if requests fail
- All changes are committed to git
- **Videos are never downloaded** - YouTube URLs processed directly by Gemini API
