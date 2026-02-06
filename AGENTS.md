# YuhHearDem - Agent's Guide

This repository focuses on scraping and ingestion for the Barbados Parliamentary Knowledge Graph.
The web UI and API have been moved to a separate package.

## Project Overview

YuhHearDem ingests parliamentary order papers and YouTube session videos to build a searchable
knowledge graph with transcripts, entities, and relationships.

**Tech Stack:**
- **Ingestion**: Python 3.13 scripts (async)
- **Database**: PostgreSQL 16 with pgvector
- **NLP**: spaCy, Google Gemini API, sentence-transformers

## IMPORTANT: No Video Downloads Policy

At no point should this system download video files. All video processing must use YouTube URLs
directly with the Gemini API.

## Directory Structure

```
YuhHearDem/
├── core/               # Shared utilities (config, DB, logging)
├── data/               # Raw data files (not in git)
├── docs/               # Documentation
├── models/             # SQLAlchemy models
├── parsers/            # Document parsers
├── processed/          # Processed data output
├── scripts/            # Scraping + ingestion tools
├── services/           # Business logic services
├── storage/            # Knowledge graph storage
├── tests/              # Test suite
├── .env.example        # Environment template
├── README.md           # Project overview and quick start
├── QUICKSTART.md       # Step-by-step local setup
├── USAGE.md            # Usage examples
└── requirements.txt    # Python dependencies
```

## Key Files Reference

### Entry Points

| File | Purpose |
|------|---------|
| `scripts/ingest_order_paper.py` | PDF ingestion CLI |
| `scripts/ingest_video.py` | Video ingestion CLI |
| `scripts/run_full_ingestion.py` | Full ingestion pipeline |
| `scripts/daily_pipeline.py` | Daily automation |
| `scripts/scrape_session_papers.py` | Web scraper |

### Configuration

| File | Purpose |
|------|---------|
| `core/config.py` | Pydantic settings |
| `core/database.py` | Database engine + sessions |
| `.env.example` | Environment template |

## Data Flow Overview

```
Order Paper (PDF) ──▶ OrderPaperParser ──▶ order_papers + speakers
YouTube URL ─────────▶ VideoTranscription ─▶ transcripts + entities + relationships
```

## Common Tasks

### Ingest Order Papers

```bash
python scripts/ingest_order_paper.py data/papers/session_paper.pdf
```

### Ingest Videos

```bash
python scripts/ingest_video.py --mapping data/video_mapping.json
```

### Run Tests

```bash
pytest
```

## Environment Variables

### Required

| Variable | Purpose | Example |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://user:pass@localhost/yuhheardem` |
| `GOOGLE_API_KEY` | Gemini API access | `your_api_key_here` |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `APP_ENV` | Environment | `development` |
| `DEBUG` | Debug mode | `True` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `FUZZY_MATCH_THRESHOLD` | Fuzzy matching threshold | `85` |
| `EMBEDDING_MODEL` | Embedding model | `all-MiniLM-L6-v2` |

## Notes for AI Agents

1. Keep ingestion scripts fast and robust.
2. Prefer real DB sessions over mocks unless external APIs are involved.
3. Update docs when you change ingestion behavior.
4. Never download YouTube videos.
