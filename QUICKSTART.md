# Quick Start Guide

This guide walks you through getting YuhHearDem running with real data.

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your GOOGLE_API_KEY and DATABASE_URL
   ```

3. **Start PostgreSQL:**
   ```bash
   docker-compose up -d
   ```

4. **Run migrations:**
   ```bash
   source venv/bin/activate
   alembic upgrade head
   ```

## Ingestion Options

### Option 1: Full Pipeline (Automatic)

Fastest way to get started:

```bash
# Step 1: Create video URL list
echo "https://www.youtube.com/watch?v=VIDEO_ID_1" > data/videos/urls.txt
echo "https://www.youtube.com/watch?v=VIDEO_ID_2" >> data/videos/urls.txt

# Step 2: Run full pipeline
python scripts/run_full_ingestion.py --download-videos
```

This will:
1. Scrape session papers from parliament website
2. Download PDFs to `data/papers/`
3. Parse PDFs with Gemini Vision
4. Download YouTube videos to `data/videos/`
5. Transcribe videos with Gemini
6. Extract entities and relationships
7. Save everything to database

### Option 2: Manual Step-by-Step

For more control, run each step manually:

#### Step 1: Download Order Papers

Option A: Scrape from website
```bash
python scripts/scrape_session_papers.py --download
```

Option B: Manually download PDFs
- Go to parliament website
- Download session papers to `data/papers/`

#### Step 2: Ingest Order Papers

```bash
# Single file
python scripts/ingest_order_paper.py data/papers/session_paper.pdf

# All files in directory
python scripts/ingest_order_paper.py data/papers/
```

#### Step 3: Download YouTube Videos

Option A: Download with script
```bash
# Create URL list
echo "https://www.youtube.com/watch?v=VIDEO_ID" > data/videos/urls.txt

# Download
python scripts/download_youtube_videos.py --list data/videos/urls.txt
```

Option B: Manually download
- Use yt-dlp or browser
- Save to `data/videos/`

#### Step 4: Transcribe Videos

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

Then ingest:
```bash
python scripts/ingest_video.py --mapping data/video_ingest_mapping.json
```

## Start the Application

Once data is ingested:

```bash
# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Access the Interface

Open your browser to:

1. **Chat Interface**: http://localhost:8000/static/chat.html
   - Ask questions about parliamentary sessions
   - Get answers with citations
   - View related entities

2. **Graph Visualization**: http://localhost:8000/static/graph.html
   - See entity relationships
   - Explore knowledge graph

3. **API Documentation**: http://localhost:8000/docs
   - Interactive API explorer
   - Test endpoints

## Example Queries

Try these questions in the chat interface:

- "What legislation was discussed on January 15, 2024?"
- "Who spoke about the Cybercrime Bill?"
- "Show me all mentions of the Finance Minister"
- "What topics were covered in recent sessions?"
- "What entities are related to tax policy?"

## Tips

1. **Start small**: Ingest 1-2 videos first to test the pipeline
2. **Use audio-only**: For faster downloads, use `--audio-only` flag
3. **Check API quota**: Gemini has rate limits, start with smaller batches
4. **Verify data**: After ingestion, check database:
   ```bash
   python -c "
   from sqlalchemy import select
   from models.video import Video
   from app.dependencies import get_db_session
   import asyncio

   async def check():
       async with get_db_session() as db:
           result = await db.execute(select(Video))
           print(f'Videos in DB: {len(result.scalars().all())}')
   asyncio.run(check())
   "
   ```

## Troubleshooting

### "Module not found" errors

Make sure you're in the virtual environment:
```bash
source venv/bin/activate
```

### "Database connection failed"

Check PostgreSQL is running:
```bash
docker-compose ps
# Restart if needed
docker-compose restart
```

### "API quota exceeded"

Wait a few hours or check your Google Cloud billing:
https://console.cloud.google.com/apis/library/generative-language-api

### Scraper can't find papers

The scraper is a template. You may need to:
1. Check actual parliament website structure
2. Update URL patterns in `scripts/scrape_session_papers.py`
3. Or manually download PDFs

## Next Steps

Once you have data ingested:

1. Explore the chat interface
2. Check the knowledge graph visualization
3. Try different query types
4. Add more data as needed

For more details, see:
- `scripts/README.md` - Detailed script documentation
- `README.md` - Full project documentation
