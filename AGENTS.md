# YuhHearDem - Agent's Guide

This document provides a comprehensive guide to the YuhHearDem codebase, designed for AI agents and developers working on this project.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Codebase Map](#codebase-map)
3. [Directory Structure](#directory-structure)
4. [Key Files Reference](#key-files-reference)
5. [Architecture Overview](#architecture-overview)
6. [Service Layer](#service-layer)
7. [Data Models](#data-models)
8. [API Layer](#api-layer)
9. [Scripts & Tools](#scripts--tools)
10. [Testing](#testing)
11. [Deployment](#deployment)
12. [Documentation Index](#documentation-index)

---

## Project Overview

YuhHearDem is a Barbados Parliamentary Knowledge Graph system that processes parliamentary proceedings (videos and documents) to create a searchable, queryable knowledge base using NLP and AI techniques.

**Tech Stack:**
- **Backend:** FastAPI with Python 3.13+
- **Database:** PostgreSQL 16 with pgvector extension
- **NLP:** spaCy, Google Gemini API, sentence-transformers
- **Frontend:** Vanilla JavaScript with Tailwind CSS
- **Deployment:** Docker with blue-green strategy, nginx, GitHub Actions

---

## IMPORTANT: No Video Downloads Policy

**CRITICAL:** At no point should this system EVER download video files. All video processing must use YouTube URLs directly with the Gemini API.

**Why:**
- Gemini API can process YouTube videos directly via `file_uri` parameter
- Downloading videos wastes disk space and bandwidth
- YouTube URLs are more efficient and don't require local storage
- Processing YouTube URLs directly is faster and more scalable

**Implementation:**
- All transcription services pass `video_url` (YouTube URL) directly to Gemini
- The `analyze_video_with_transcript()` method uses `file_uri=video_url`
- No local video files are ever created or stored
- The `data/videos/` directory should remain empty

**Previous download scripts removed:**
- `scripts/download_youtube_videos.py` - REMOVED
- `scripts/simple_download_video.py` - REMOVED
- Video download functionality from `run_full_ingestion.py` - REMOVED

---

## Codebase Map

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            YUHHEARDEM SYSTEM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   API Layer  │  │  Service     │  │   Models     │  │   Storage    │     │
│  │   (FastAPI)  │  │  Layer       │  │  (SQLAlchemy)│  │  (PostgreSQL)│     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │             │
│         │ Routes          │ Business Logic  │ Data Layer      │ Persistence │
│         │ - chat.py       │ - transcription │ - video.py      │             │
│         │ - search.py     │ - extraction    │ - speaker.py    │             │
│         │ - videos.py     │ - embeddings    │ - entity.py     │             │
│         └─────────────────┴─────────────────┴─────────────────┘             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         SCRIPTS                                     │   │
│  │  - ingest_order_paper.py  - ingest_video.py                         │   │
│  │  - scrape_session_papers.py  - run_full_ingestion.py               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         PARSERS                                     │   │
│  │  - order_paper_parser.py  - video_transcript.py                     │   │
│  │  - transcript_models.py  - models.py                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
YuhHearDem/
├── api/                          # API layer (routes and schemas)
│   ├── routes/                   # FastAPI route handlers
│   │   ├── __init__.py
│   │   ├── chat.py               # Chat/query endpoints
│   │   ├── search.py             # Search endpoints
│   │   └── videos.py             # Video management endpoints
│   └── schemas.py                # Pydantic models for API
│
├── app/                          # FastAPI application core
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── dependencies.py           # FastAPI dependencies
│   ├── main.py                   # Application entry point
│   └── middleware.py             # Custom middleware
│
├── core/                         # Core utilities
│   ├── __init__.py
│   ├── database.py               # Database connection and session
│   └── logging_config.py         # Logging configuration
│
├── data/                         # Data files (not in git)
│   ├── papers/                   # Order paper PDFs
│   └── videos/                   # Video directory (should remain empty - no downloads)
│
├── deploy/                       # Deployment configuration
│   ├── deploy.sh                 # Blue-green deployment script
│   ├── docker-compose.blue.yml   # Blue slot configuration
│   ├── docker-compose.green.yml  # Green slot configuration
│   ├── docker-compose.postgres.yml  # Database configuration
│   ├── migrate.sh                # Migration script
│   ├── nginx.conf                # Nginx configuration
│   └── setup.sh                  # Initial server setup
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE_ANALYSIS.md  # System architecture analysis
│   ├── DEPLOYMENT_IMPLEMENTATION.md  # Deployment details
│   ├── DEPLOYMENT_QUICKSTART.md  # Deployment quickstart
│   ├── GITHUB_SECRETS.md         # GitHub secrets setup
│   ├── REBUILD_PLAN.md           # Original rebuild plan
│   └── deployment.md             # Deployment guide
│
├── migrations/                   # Alembic database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                 # Migration files
│       ├── 001_initial_schema.py
│       ├── 002_add_speaker_canonical_id.py
│       ├── 003_add_kg_provenance_fields.py
│       └── 004_add_transcript_segments.py
│
├── models/                       # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── entity.py                 # Knowledge graph entities
│   ├── legislation.py            # Legislation/bills
│   ├── mention.py                # Entity mentions
│   ├── message.py                # Chat messages
│   ├── order_paper.py            # Order papers
│   ├── relationship.py           # Entity relationships
│   ├── session.py                # User sessions
│   ├── speaker.py                # Parliamentary speakers
│   ├── transcript_segment.py     # Transcript segments
│   ├── vector_embedding.py       # Vector embeddings
│   └── video.py                  # Video records
│
├── parsers/                      # Data parsers
│   ├── __init__.py
│   ├── models.py                 # Parser data models
│   ├── order_paper_parser.py     # PDF order paper parser
│   ├── transcript_models.py      # Transcript data models
│   └── video_transcript.py       # Video transcription parser
│
├── processed/                    # Processed data output
│
├── scripts/                      # Utility scripts
│   ├── __init__.py
│   ├── daily_pipeline.py         # Daily automation
│   ├── ingest_order_paper.py     # Order paper ingestion
│   ├── ingest_video.py           # Video ingestion
│   ├── match_videos_to_papers.py # Video-paper matcher
│   ├── scrape_session_papers.py  # Web scraper
│   └── test_api.py               # API test script
│
├── services/                     # Business logic services
│   ├── __init__.py
│   ├── embeddings.py             # Vector embeddings
│   ├── entity_extractor.py       # Entity extraction
│   ├── gemini.py                 # Gemini API wrapper
│   ├── parliamentary_agent.py    # Agentic RAG system
│   ├── parliamentary_agent_tools.py  # Agent tools
│   ├── speaker_matcher.py        # Speaker matching
│   ├── transcript_segmenter.py   # Transcript segmentation
│   ├── video_paper_matcher.py    # Video/paper matching
│   └── video_transcription.py    # Video transcription
│
├── static/                       # Static web assets
│   ├── chat.html                 # Chat interface
│   ├── graph.html                # Graph visualization
│   ├── index.html                # Main page
│   ├── css/                      # Stylesheets
│   └── js/                       # JavaScript files
│
├── storage/                      # Storage layer
│   ├── __init__.py
│   └── knowledge_graph_store.py  # Knowledge graph storage
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   ├── factories.py              # Test factories
│   ├── test_api/                 # API tests
│   │   ├── test_chat.py
│   │   └── test_root.py
│   ├── test_integration/         # Integration tests
│   │   └── test_agentic_chat_integration.py
│   ├── test_migrations/          # Migration tests
│   │   └── test_speaker_schema_migration.py
│   ├── test_models/              # Model tests
│   │   └── test_transcript_segment.py
│   ├── test_scripts/             # Script tests
│   │   ├── test_ingest_video_db_context.py
│   │   └── test_ingest_video_help.py
│   └── test_services/            # Service tests
│       ├── __init__.py
│       ├── test_embeddings.py
│       ├── test_entity_extractor_speakers.py
│       ├── test_gemini_usage.py
│       ├── test_knowledge_graph_store.py
│       ├── test_parliamentary_agent.py
│       ├── test_speaker_matcher.py
│       ├── test_video_ingestor.py
│       ├── test_video_transcription.py
│       └── test_video_transcription_timing.py
│
├── .env.example                  # Environment template
├── AGENTS.md                     # This file
├── Dockerfile                    # Docker image definition
├── QUICKSTART.md                 # Quick start guide
├── README.md                     # Project readme
├── USAGE.md                      # Usage documentation
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Local Docker setup
├── fix_migration.py              # Migration fix script
├── pyproject.toml                # Python project config
├── pytest.ini                    # Pytest configuration
└── requirements.txt              # Python dependencies
```

---

## Key Files Reference

### Entry Points

| File | Purpose | Notes |
|------|---------|-------|
| `app/main.py` | FastAPI application entry | Creates FastAPI app, mounts routers |
| `scripts/ingest_video.py` | Video ingestion CLI | Main script for adding videos |
| `scripts/ingest_order_paper.py` | PDF ingestion CLI | Main script for adding order papers |
| `scripts/run_full_ingestion.py` | Full pipeline | Orchestrates complete ingestion |

### Configuration

| File | Purpose | Notes |
|------|---------|-------|
| `app/config.py` | Application settings | Pydantic Settings with env var support |
| `alembic.ini` | Database migrations | Alembic configuration |
| `pyproject.toml` | Project metadata | Build system, tool configs |
| `.env.example` | Environment template | Copy to .env and customize |

### Core Services

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `services/parliamentary_agent.py` | Agentic RAG system | `ParliamentaryAgent`, `process_query()` |
| `services/entity_extractor.py` | Entity extraction | `EntityExtractor`, `extract()` |
| `services/video_transcription.py` | Video transcription | `VideoTranscriptionService` |
| `services/embeddings.py` | Vector embeddings | `EmbeddingService` |
| `services/speaker_matcher.py` | Speaker matching | `SpeakerMatcher` |

### API Routes

| File | Endpoints | Purpose |
|------|-----------|---------|
| `api/routes/chat.py` | `/api/query`, `/api/query/stream` | Chat interface |
| `api/routes/search.py` | `/api/search` | Semantic search |
| `api/routes/videos.py` | `/api/videos` | Video management |

### Data Models (SQLAlchemy)

| File | Table | Key Columns |
|------|-------|-------------|
| `models/video.py` | `videos` | youtube_id, title, transcript, chamber |
| `models/speaker.py` | `speakers` | canonical_id, name, aliases, chamber |
| `models/entity.py` | `entities` | entity_id, entity_type, name, importance_score |
| `models/relationship.py` | `relationships` | source_id, target_id, relation_type, evidence |
| `models/order_paper.py` | `order_papers` | pdf_path, session_date, speakers, agenda_items |

---

## Architecture Overview

### Data Flow

```
Order Paper (PDF) ───────┐
                         │
                         ▼
              ┌──────────────────────┐
              │ OrderPaperParser     │  (Gemini Vision API)
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Speakers + Agenda    │  (OrderPaper model)
              └──────────┬───────────┘
                         │
                         ▼
YouTube Video ──────────▶│
                         │
                         ▼
              ┌──────────────────────┐
              │ VideoTranscription   │  (Gemini Video API)
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Transcript + Entities│  (Entity extraction)
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ PostgreSQL + pgvector│  (Persistent storage)
              └──────────────────────┘
```

### Component Interactions

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   API Routes    │────▶│     Services     │────▶│  Data Models    │
│                 │     │                  │     │                 │
│ - chat.py       │     │ - parliamentary_ │     │ - video.py      │
│ - search.py     │     │   agent.py       │     │ - speaker.py    │
│ - videos.py     │     │ - entity_        │     │ - entity.py     │
└─────────────────┘     │   extractor.py   │     │ - mention.py    │
                        │ - embeddings.py  │     │ - relationship. │
                        └────────┬─────────┘     │   py            │
                                 │               └─────────────────┘
                                 ▼                       │
                        ┌──────────────────┐            │
                        │ External APIs    │            │
                        │                  │            │
                        │ - Gemini API     │            │
                        │ - YouTube        │            │
                        └──────────────────┘            │
                                                        ▼
                                               ┌──────────────────┐
                                               │  PostgreSQL      │
                                               │  + pgvector      │
                                               └──────────────────┘
```

---

## Service Layer

### Core Services

#### 1. ParliamentaryAgent (`services/parliamentary_agent.py`)

**Purpose:** Agentic RAG system for natural language queries.

**Key Methods:**
- `process_query()` - Main entry point for queries
- Uses function calling with Gemini API
- Tools: find_entity, get_relationships, get_mentions, search_semantic

**Usage:**
```python
from services.parliamentary_agent import ParliamentaryAgent

agent = ParliamentaryAgent()
response = await agent.process_query(
    query="What did Senator Cummins say about CARICOM?",
    user_id="user-123",
    session_id="session-456"
)
```

#### 2. EntityExtractor (`services/entity_extractor.py`)

**Purpose:** Extract entities and relationships from transcripts.

**Key Methods:**
- `extract()` - Two-pass extraction (entities then relationships)
- Uses spaCy for preprocessing (optional)
- Saves to knowledge graph store

**Usage:**
```python
from services.entity_extractor import EntityExtractor

extractor = EntityExtractor()
entities = await extractor.extract(transcript_data, video_id="video-123")
```

#### 3. VideoTranscriptionService (`services/video_transcription.py`)

**Purpose:** Transcribe videos with speaker attribution.

**Key Methods:**
- `transcribe()` - Main transcription method
- Supports chunking for long videos
- Integrates order paper for context

**Usage:**
```python
from services.video_transcription import VideoTranscriptionService

service = VideoTranscriptionService()
transcript = await service.transcribe(
    youtube_url="https://youtube.com/watch?v=...",
    order_paper=order_paper_data
)
```

#### 4. EmbeddingService (`services/embeddings.py`)

**Purpose:** Generate and manage vector embeddings.

**Key Methods:**
- `embed_text()` - Generate embeddings
- `search_similar()` - Semantic search
- Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

#### 5. SpeakerMatcher (`services/speaker_matcher.py`)

**Purpose:** Match speakers across sessions, handle name variations.

**Key Methods:**
- `match_speaker()` - Find or create speaker
- Uses fuzzy matching with configurable threshold (default 85%)
- Normalizes names (removes titles, lowercases)

---

## Data Models

### Entity Relationships

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│   videos    │       │   speakers   │       │ order_papers│
├─────────────┤       ├──────────────┤       ├─────────────┤
│ id (PK)     │◀──────│ id (PK)      │       │ id (PK)     │
│ youtube_id  │       │ canonical_id │       │ video_id(FK)│
│ title       │       │ name         │       │ pdf_path    │
│ transcript  │       │ aliases      │       │ speakers    │
│ chamber     │       │ chamber      │       │ agenda_items│
│ session_date│       │ role         │       └─────────────┘
└──────┬──────┘       └──────────────┘
       │
       │ 1:N
       ▼
┌─────────────────────────────────────────────────────────┐
│                     KNOWLEDGE GRAPH                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐      ┌──────────────┐                 │
│  │  entities   │◀────▶│relationships │                 │
│  ├─────────────┤  N:M ├──────────────┤                 │
│  │ id (PK)     │      │ id (PK)      │                 │
│  │ entity_id   │      │ source_id(FK)│                 │
│  │ entity_type │      │ target_id(FK)│                 │
│  │ name        │      │ relation_type│                 │
│  │ importance  │      │ evidence     │                 │
│  └──────┬──────┘      │ confidence   │                 │
│         │             └──────────────┘                 │
│         │ 1:N                                          │
│         ▼                                              │
│  ┌─────────────┐                                       │
│  │  mentions   │                                       │
│  ├─────────────┤                                       │
│  │ id (PK)     │                                       │
│  │ entity_id   │                                       │
│  │ video_id    │                                       │
│  │ timestamp   │                                       │
│  │ context     │                                       │
│  └─────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

---

## API Layer

### Route Structure

All routes are mounted in `app/main.py`:

```python
app.include_router(videos.router)
app.include_router(search.router)
app.include_router(chat.router)
```

### Endpoints

#### Chat API (`api/routes/chat.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/query` | Process natural language query |
| POST | `/api/query/stream` | Streaming query response (SSE) |

#### Search API (`api/routes/search.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search` | Semantic search across transcripts |

#### Video API (`api/routes/videos.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/videos` | List all videos |
| GET | `/api/videos/{video_id}` | Get video details |
| POST | `/api/videos` | Create new video record |

### Static Files

Static files served from `/static`:
- `/static/chat.html` - Chat interface
- `/static/graph.html` - Graph visualization
- `/static/index.html` - Main page

---

## Scripts & Tools

### Data Ingestion Scripts

| Script | Purpose | Key Args |
|--------|---------|----------|
| `ingest_order_paper.py` | Parse PDFs with Gemini | `PDF_PATH` |
| `ingest_video.py` | Transcribe videos | `--url`, `--mapping` |
| `scrape_session_papers.py` | Scrape parliament website | `--download` |
| `run_full_ingestion.py` | Full pipeline | `--chamber`, `--max-papers` |

### Usage Examples

**Ingest order paper:**
```bash
python scripts/ingest_order_paper.py data/papers/session.pdf
```

**Ingest video:**
```bash
python scripts/ingest_video.py \
  --url https://youtube.com/watch?v=VIDEO_ID \
  --session-date 2024-01-15 \
  --chamber house
```

**Run full pipeline:**
```bash
python scripts/run_full_ingestion.py --chamber house --max-papers 10
```

---

## Testing

### Test Organization

```
tests/
├── test_api/           # API endpoint tests
├── test_integration/   # Integration tests
├── test_migrations/    # Database migration tests
├── test_models/        # ORM model tests
├── test_scripts/       # Script tests
└── test_services/      # Service unit tests
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov=core --cov=services --cov-report=html

# Specific test file
pytest tests/test_services/test_parliamentary_agent.py

# With markers
pytest -m unit
pytest -m integration
```

### Test Configuration

See `pytest.ini` for markers and configuration.

---

## Deployment

### Blue-Green Deployment

```
                    Nginx (443)
                         │
         ┌───────────────┴───────────────┐
         │                               │
    Blue Slot (8003)              Green Slot (8013)
         │                               │
         └───────────────┬───────────────┘
                         │
                   PostgreSQL (5432)
```

### Deployment Commands

```bash
# Deploy latest
sudo ./deploy/deploy.sh latest

# Deploy specific version
sudo ./deploy/deploy.sh sha-abc123def

# Check status
sudo ./deploy/deploy.sh status

# Rollback
sudo ./deploy/deploy.sh rollback
```

### Environment Files

| File | Purpose |
|------|---------|
| `.env` | Local development |
| `.env.production.example` | Production template |

---

## Documentation Index

| Document | Purpose | Audience |
|----------|---------|----------|
| `README.md` | Project overview, quick start | Everyone |
| `QUICKSTART.md` | Step-by-step setup guide | New users |
| `USAGE.md` | Usage examples and scripts | Users |
| `AGENTS.md` | This file - codebase map | AI agents, developers |
| `scripts/README.md` | Script documentation | Users |
| `docs/ARCHITECTURE_ANALYSIS.md` | System architecture | Developers |
| `docs/REBUILD_PLAN.md` | Original rebuild plan | Developers |
| `docs/deployment.md` | Deployment guide | DevOps |
| `docs/DEPLOYMENT_QUICKSTART.md` | Quick deployment | DevOps |
| `docs/DEPLOYMENT_IMPLEMENTATION.md` | Deployment details | DevOps |
| `docs/GITHUB_SECRETS.md` | GitHub secrets setup | DevOps |

---

## Common Tasks

### Adding a New Entity Type

1. Update `models/entity.py` - Add to EntityType enum
2. Update `parsers/models.py` - Add parser support
3. Update `services/entity_extractor.py` - Handle in extraction
4. Run migrations: `alembic revision --autogenerate -m "Add entity type"`

### Adding a New API Endpoint

1. Add route handler in `api/routes/<module>.py`
2. Add schema in `api/schemas.py` if needed
3. Include router in `app/main.py`
4. Add tests in `tests/test_api/`

### Adding a New Service

1. Create file in `services/<service_name>.py`
2. Follow existing service patterns
3. Add tests in `tests/test_services/`
4. Update this AGENTS.md with service details

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one
alembic downgrade -1

# View history
alembic history
```

---

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
| `CORS_ORIGINS` | Allowed origins | `["http://localhost:3000"]` |
| `FUZZY_MATCH_THRESHOLD` | Fuzzy matching threshold | `85` |
| `EMBEDDING_MODEL` | Embedding model | `all-MiniLM-L6-v2` |

---

## Dependencies

### Core

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy[asyncio]` - ORM
- `asyncpg` - PostgreSQL driver
- `pgvector` - Vector extension support
- `alembic` - Database migrations

### AI/NLP

- `google-genai` - Gemini API
- `spacy` - NLP processing
- `sentence-transformers` - Embeddings
- `thefuzz` - Fuzzy string matching

### Utilities

- `pydantic` - Data validation
- `python-dotenv` - Environment variables
- `httpx` - HTTP client
- `yt-dlp` - YouTube downloading

---

## Notes for AI Agents

1. **Always check for tests first** - When modifying code, check if tests exist and run them
2. **Follow existing patterns** - Look at similar files for code style and patterns
3. **Update documentation** - When adding features, update relevant docs
4. **Database migrations** - Any model changes require Alembic migrations
5. **Type hints** - Use proper type hints throughout (Python 3.13+)
6. **Async/await** - Most services use async/await pattern
7. **Error handling** - Use try/except blocks and proper logging
8. **Environment** - Never hardcode secrets, use environment variables

---

**Document Version:** 1.0  
**Last Updated:** 2025-02-04  
**Author:** Codebase Analysis
