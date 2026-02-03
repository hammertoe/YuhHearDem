# Ingestion Scripts

Complete pipeline for scraping, parsing, and ingesting Barbados parliamentary data.

## Prerequisites

Install additional dependencies:
```bash
pip install yt-dlp requests beautifulsoup4
```

Environment variables must be set in `.env`:
```bash
GOOGLE_API_KEY=your_gemini_api_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/yuhheardem
```

## Quick Start

### 1. Run Full Pipeline (Recommended)

Scrapes session papers, downloads them, parses with Gemini, and saves to database:

```bash
# Scrape and ingest order papers
python scripts/run_full_ingestion.py

# With video download (requires data/videos/urls.txt)
python scripts/run_full_ingestion.py --download-videos
```

### 2. Individual Steps

#### Scrape Session Papers

```bash
# List available papers
python scripts/scrape_session_papers.py

# Download PDFs
python scripts/scrape_session_papers.py --download

# Specific chamber
python scripts/scrape_session_papers.py --chamber senate --download
```

#### Download YouTube Videos

```bash
# Single video
python scripts/download_youtube_videos.py https://www.youtube.com/watch?v=VIDEO_ID

# From list file (one URL per line)
python scripts/download_youtube_videos.py --list data/videos/urls.txt

# Audio only (faster, smaller files)
python scripts/download_youtube_videos.py --list data/videos/urls.txt --audio-only
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
# Single video URL
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

## Workflow

### Complete Workflow

1. **Create directories:**
   ```bash
   mkdir -p data/papers data/videos
   ```

2. **Download videos manually (optional):**
   - Go to Barbados Parliament YouTube channel
   - Copy URLs to `data/videos/urls.txt` (one per line)

3. **Run full pipeline:**
   ```bash
   python scripts/run_full_ingestion.py --download-videos
   ```

### Manual Workflow

For more control, run steps individually:

1. **Scrape session papers:**
   ```bash
   python scripts/scrape_session_papers.py --download --output data/papers
   ```

2. **Download videos manually:**
   ```bash
   python scripts/download_youtube_videos.py --list data/videos/urls.txt
   ```

3. **Ingest order papers:**
   ```bash
   python scripts/ingest_order_paper.py data/papers/
   ```

4. **Create video mapping** (matches PDFs to videos):
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

5. **Ingest videos:**
   ```bash
   python scripts/ingest_video.py --mapping data/video_ingest_mapping.json
   ```

## Script Details

### `run_full_ingestion.py`

Orchestrates complete pipeline.

**Options:**
- `--chamber`: house or senate (default: house)
- `--max-papers`: Max order papers to scrape
- `--max-videos`: Max videos to download
- `--download-videos`: Download YouTube videos
- `--output`: Output directory (default: data/)

### `scrape_session_papers.py`

Scrapes session papers from parliament website.

**Note:** You may need to adjust URL patterns and selectors based on actual website structure. The current implementation is a template.

### `download_youtube_videos.py`

Downloads YouTube videos with metadata.

**Options:**
- `--audio-only`: Extract audio only (faster)
- `--list`: File with URLs
- `--output`: Output directory

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

## Troubleshooting

### Scraper Issues

If session papers don't scrape:
1. Check parliament website is accessible
2. Inspect HTML structure and update selectors in `scrape_session_papers.py`
3. Download PDFs manually if needed

### Video Download Issues

If YouTube downloads fail:
1. Ensure `yt-dlp` is installed and updated: `pip install --upgrade yt-dlp`
2. Check internet connectivity
3. Verify URLs are valid
4. Try `--audio-only` for smaller files

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
