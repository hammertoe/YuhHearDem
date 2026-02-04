# Quick Start Guide

This guide walks you through getting YuhHearDem running with real data.

**Related Documentation**:
- [README.md](./README.md) - Project overview
- [AGENTS.md](./AGENTS.md) - Comprehensive codebase guide with code map
- [scripts/README.md](./scripts/README.md) - Detailed script documentation
- [USAGE.md](./USAGE.md) - Usage examples

**Important**: This system processes YouTube videos by passing URLs directly to the Gemini API. Video files are never downloaded locally. See [AGENTS.md](../AGENTS.md) for details.

## Step 1: Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY and DATABASE_URL

# Start PostgreSQL
docker-compose up -d

# Run migrations
alembic upgrade head
```

## Step 2: Get Data

### Option A: Manual (Recommended for getting started)

1. **Download order papers:**
   - Go to: https://www.barbadosparliament.com/order_papers/search
   - Click "House of Assembly" or "The Senate"
   - Download PDFs to `data/papers/`

2. **Get YouTube video URLs:**
   - Go to Barbados Parliament YouTube channel
   - Copy video URLs (these will be processed directly by Gemini - no download needed)

```bash
mkdir -p data/papers
```

### Option B: Automated

```bash
# Scrape and download papers
python scripts/scrape_session_papers.py --download

# The scraper finds papers and downloads PDFs to data/papers/
```

**Note:** The scraper may need adjustments based on website structure. Manual download is often faster and more reliable.

## Step 3: Ingest Data

Once you have PDFs and video URLs:

### Ingest Order Papers

```bash
# Ingest a single PDF
python scripts/ingest_order_paper.py data/papers/session_paper.pdf

# Or ingest all PDFs from directory
python scripts/ingest_order_paper.py data/papers/
```

This will:
- Parse PDF with Gemini Vision API
- Extract speakers and agenda items
- Save to database
- Create speaker records

### Ingest Videos

First, create a mapping file `data/video_mapping.json`:
```json
[
    {
        "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
        "chamber": "house",
        "session_date": "2024-01-15",
        "order_paper_pdf": "data/papers/session_paper.pdf"
    }
]
```

Then ingest (YouTube URL processed directly by Gemini - no download needed):
```bash
python scripts/ingest_video.py --mapping data/video_mapping.json
```

## Step 4: Start Application

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

### Order Paper Ingestion
1. Reads PDF file
2. Sends to Gemini Vision API
3. Extracts:
   - Session title and date
   - List of all speakers
   - Agenda items and topics
4. Saves to `order_papers` table
5. Creates/updates speaker records

### Video Ingestion
1. **Passes YouTube URL directly to Gemini Video API** (no download)
2. Transcribes with speaker attribution
3. Extracts entities from transcript
4. Saves to `videos` table
5. Links to order papers if provided

### Entity Extraction
Automatically happens during video transcription:
1. Identifies people, organizations, legislation
2. Creates entity records
3. Finds relationships between entities
4. Builds knowledge graph

## Next Steps

Once you have data ingested:

1. Explore the chat interface
2. Check the knowledge graph visualization
3. Try different query types
4. Add more data as needed

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
| [ARCHITECTURE_ANALYSIS.md](./docs/ARCHITECTURE_ANALYSIS.md) | System architecture |
| [deployment.md](./docs/deployment.md) | Deployment guide |
