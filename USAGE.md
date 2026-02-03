# YuhHearDem - Usage Summary

## What Was Created

Complete data ingestion pipeline with the following scripts:

### Scripts
- `scrape_session_papers.py` - Scrapes session papers from parliament website
- `download_youtube_videos.py` - Downloads YouTube videos (with yt-dlp)
- `simple_download_video.py` - Simple YouTube download example
- `ingest_order_paper.py` - Parses PDFs & saves to database
- `ingest_video.py` - Transcribes videos & saves to database
- `run_full_ingestion.py` - Orchestrates full pipeline

### Documentation
- `scripts/README.md` - Detailed script documentation
- `QUICKSTART.md` - Step-by-step getting started guide

## How to Use

### Option 1: Quick Start (Recommended)

**Step 1: Download Session Papers**
```bash
# Go to: https://www.barbadosparliament.com/order_papers/search
# Click "House of Assembly" tab
# Download PDFs to: data/papers/
```

**Step 2: Download YouTube Videos**
```bash
# Go to Barbados Parliament YouTube channel
# Create URL list
echo "https://www.youtube.com/watch?v=VIDEO_ID" > data/videos/urls.txt

# Download
source venv/bin/activate
python scripts/simple_download_video.py 'https://www.youtube.com/watch?v=VIDEO_ID'
```

**Step 3: Ingest to Database**
```bash
# Ingest order papers
python scripts/ingest_order_paper.py data/papers/

# Create mapping file for videos
# Create: data/video_mapping.json
# Format: See below

# Ingest videos
python scripts/ingest_video.py --mapping data/video_mapping.json
```

**Step 4: Start Application**
```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

**Access Interface:**
- Chat: http://localhost:8000/static/chat.html
- Graph: http://localhost:8000/static/graph.html
- API Docs: http://localhost:8000/docs

### Option 2: Full Pipeline (Advanced)

```bash
# Attempt full pipeline
python scripts/run_full_ingestion.py --download-videos
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

### 2. download_youtube_videos.py / simple_download_video.py

- Downloads YouTube videos with metadata
- Saves to `data/videos/`
- Extracts: title, duration, channel
- Usage: `python scripts/simple_download_video.py URL`

### 3. ingest_order_paper.py

- Parses PDF with Gemini Vision API
- Extracts: session title, date, speakers, agenda items
- Saves to `order_papers` table
- Creates speaker records
- Usage: `python scripts/ingest_order_paper.py PDF_PATH`

### 4. ingest_video.py

- Transcribes YouTube video with Gemini API
- Extracts entities from transcript
- Saves to `videos` table
- Links to order papers if provided
- Usage: `python scripts/ingest_video.py --mapping MAPPING_FILE`

## Troubleshooting

### YouTube URL Issues

The shell may truncate URLs. Try these approaches:

**Option A: Use quotes**
```bash
python scripts/simple_download_video.py 'https://www.youtube.com/watch?v=ID'
```

**Option B: Use environment variable**
```bash
export VIDEO_URL="https://www.youtube.com/watch?v=ID"
python scripts/simple_download_video.py "$VIDEO_URL"
```

**Option C: Put URL in file**
```bash
echo "https://www.youtube.com/watch?v=ID" > url.txt
python scripts/simple_download_video.py $(cat url.txt)
```

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

## Next Steps

1. Download sample PDF from parliament website
2. Download sample YouTube video
3. Test ingestion with single files first
4. Start exploring via chat interface
5. Check knowledge graph visualization

## Example Workflow

```bash
# Create directories
mkdir -p data/papers data/videos

# 1. Download a session paper manually
# Visit: https://www.barbadosparliament.com/order_papers/search
# Save PDF to: data/papers/test.pdf

# 2. Ingest it
source venv/bin/activate
python scripts/ingest_order_paper.py data/papers/test.pdf

# 3. Download a video
python scripts/simple_download_video.py 'https://www.youtube.com/watch?v=SAMPLE'

# 4. Create minimal mapping
cat > data/video_mapping.json << 'EOF'
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=SAMPLE",
        "chamber": "house",
        "session_date": "2024-01-15"
    }
]
EOF

# 5. Ingest video
python scripts/ingest_video.py --mapping data/video_mapping.json

# 6. Start app
uvicorn app.main:app --reload

# 7. Open browser to: http://localhost:8000/static/chat.html
# 8. Ask: "What topics were in the session?"
```

## Notes

- The scraper is a template and may need adjustment for website changes
- Manual download of PDFs is often faster and more reliable
- Start with 1-2 test files to verify pipeline works
- Gemini API has rate limits - check quota if requests fail
- All changes are committed to git
