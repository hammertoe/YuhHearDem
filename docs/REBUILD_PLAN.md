# YuhHearDem Rebuild Plan

## Executive Summary

This plan outlines the ground-up rebuild of the YuhHearDem parliamentary transcription site using the improved architecture from the experimental rewrite. The new system will be self-hosted on a VPS with PostgreSQL + pgvector, maintaining the core functionality while improving data integrity, scalability, and maintainability.

**Timeline**: 4-6 weeks (Fast track MVP)
**Approach**: Test-Driven Development (TDD)
**Database**: PostgreSQL 16+ with pgvector extension
**Authentication**: None (anonymous sessions, like original)
**UI**: Port existing vanilla JS/Tailwind interface

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Web Server                                              │
│  ├── REST API Endpoints                                          │
│  ├── WebSocket (SSE) for streaming responses                     │
│  ├── Static File Serving (HTML/JS/CSS)                           │
│  └── Background Task Processing                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  ├── Video Transcription Service (Gemini Video API)             │
│  ├── Order Paper Processing (Gemini Vision API)                 │
│  ├── Entity Extraction Service (spaCy + LLM)                     │
│  ├── Parliamentary Agent (Agentic RAG)                           │
│  ├── Session Management                                          │
│  └── Search Service (Hybrid: pgvector + full-text)              │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL 16+ with pgvector                                    │
│  ├── videos (session transcripts)                               │
│  ├── order_papers (PDF metadata)                                 │
│  ├── entities (knowledge graph nodes)                            │
│  ├── relationships (knowledge graph edges)                       │
│  ├── mentions (entity mentions in transcripts)                  │
│  ├── speakers (canonical speaker database)                      │
│  ├── legislation (bills/resolutions metadata)                   │
│  ├── sessions (user chat sessions)                               │
│  └── vector_embeddings (pgvector for semantic search)            │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                              │
├─────────────────────────────────────────────────────────────────┤
│  ├── Gemini 2.5 Flash (AI processing)                            │
│  ├── YouTube (video source)                                      │
│  ├── Barbados Parliament Website (legislation scraping)          │
│  └── ChromaDB (optional: for persistent vector cache)           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Backend
- **Language**: Python 3.13+
- **Framework**: FastAPI with uvicorn
- **Database**: PostgreSQL 16+ with pgvector extension
- **ORM**: SQLAlchemy 2.0+ (async)
- **AI/ML**:
  - Google Gemini 2.5 Flash API
  - spaCy (en_core_web_trf)
  - sentence-transformers (all-MiniLM-L6-v2)
- **Utilities**:
  - pydantic (data validation)
  - python-dotenv (environment)
  - beautifulsoup4/lxml (scraping)
  - yt-dlp (YouTube metadata)
  - thefuzz (fuzzy matching)
  - alembic (database migrations)
  - httpx (async HTTP client)

### Frontend
- **Framework**: Vanilla JavaScript (no frameworks)
- **Styling**: Tailwind CSS (CDN)
- **Markdown**: marked.js
- **Visualization**: D3.js v7.8.5
- **Communication**: Server-Sent Events (SSE) for streaming

### Infrastructure
- **Server**: VPS (self-hosted)
- **Reverse Proxy**: Nginx
- **Process Manager**: systemd or supervisor
- **Logging**: Structured JSON logs
- **Monitoring**: Prometheus + Grafana (optional, MVP may defer)
- **Backup**: PostgreSQL WAL archiving + pg_dump

---

## Database Schema

### Core Tables

```sql
-- Videos (parliamentary sessions)
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_id VARCHAR(20) UNIQUE NOT NULL,
    youtube_url TEXT NOT NULL,
    title TEXT NOT NULL,
    chamber VARCHAR(50) NOT NULL, -- 'senate' | 'house'
    session_date DATE NOT NULL,
    sitting_number VARCHAR(50),
    duration_seconds INTEGER,
    transcript JSONB NOT NULL, -- Full transcript with timestamps
    transcript_processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_videos_youtube_id ON videos(youtube_id);
CREATE INDEX idx_videos_date ON videos(session_date DESC);
CREATE INDEX idx_videos_chamber ON videos(chamber);

-- Order Papers (PDF context)
CREATE TABLE order_papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    pdf_path TEXT NOT NULL,
    pdf_hash TEXT NOT NULL, -- For caching
    session_title TEXT,
    session_date DATE,
    sitting_number VARCHAR(50),
    chamber VARCHAR(50),
    speakers JSONB NOT NULL, -- Array of speakers from PDF
    agenda_items JSONB NOT NULL, -- Array of agenda items
    parsed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(video_id, pdf_hash)
);

CREATE INDEX idx_order_papers_video_id ON order_papers(video_id);

-- Speakers (canonical database)
CREATE TABLE speakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_id VARCHAR(100) UNIQUE NOT NULL, -- slug-based ID
    name TEXT NOT NULL,
    title TEXT, -- 'Hon.', 'Dr.', etc.
    role TEXT, -- 'Senator', 'MP', etc.
    chamber VARCHAR(50),
    aliases JSONB DEFAULT '[]'::jsonb, -- Alternative name variations
    pronoun VARCHAR(10), -- 'he', 'she', 'they'
    gender VARCHAR(20), -- 'male', 'female', 'unknown'
    first_seen_date DATE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_speakers_canonical_id ON speakers(canonical_id);
CREATE INDEX idx_speakers_name ON speakers USING GIN(to_tsvector('english', name));

-- Legislation (bills/resolutions)
CREATE TABLE legislation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    legislation_id VARCHAR(100) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    type VARCHAR(50), -- 'bill', 'resolution'
    status VARCHAR(50), -- 'first_reading', 'second_reading', etc.
    sponsors JSONB DEFAULT '[]'::jsonb,
    chamber VARCHAR(50),
    parliament_id TEXT, -- Reference to parliament session
    pdf_url TEXT,
    description TEXT,
    stages JSONB DEFAULT '[]'::jsonb,
    scraped_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_legislation_id ON legislation(legislation_id);
CREATE INDEX idx_legislation_title ON legislation USING GIN(to_tsvector('english', title));

-- Entities (knowledge graph nodes)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id VARCHAR(100) UNIQUE NOT NULL, -- Canonical ID
    entity_type VARCHAR(50) NOT NULL, -- person, organization, place, law, concept, event
    name TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases JSONB DEFAULT '[]'::jsonb,
    description TEXT,
    importance_score FLOAT DEFAULT 0.0,
    legislation_id UUID REFERENCES legislation(id),
    metadata JSONB DEFAULT '{}'::jsonb,
    first_seen_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_entities_entity_id ON entities(entity_id);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities USING GIN(to_tsvector('english', name));

-- Entity Mentions (link entities to transcripts)
CREATE TABLE mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id VARCHAR(100) REFERENCES entities(entity_id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    agenda_item_index INTEGER,
    sentence_index INTEGER,
    timestamp_seconds INTEGER,
    context TEXT, -- Surrounding sentence/text
    bill_id VARCHAR(100), -- If mentioned in bill context
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mentions_entity_id ON mentions(entity_id);
CREATE INDEX idx_mentions_video_id ON mentions(video_id);
CREATE INDEX idx_mentions_timestamp ON mentions(timestamp_seconds);

-- Relationships (knowledge graph edges)
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(100) REFERENCES entities(entity_id) ON DELETE CASCADE,
    target_id VARCHAR(100) REFERENCES entities(entity_id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL, -- mentions, supports, opposes, relates_to, references
    sentiment VARCHAR(20), -- positive, negative, neutral
    evidence TEXT NOT NULL, -- Direct quote from transcript
    confidence FLOAT,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    timestamp_seconds INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
CREATE INDEX idx_relationships_type ON relationships(relation_type);

-- Vector Embeddings (for semantic search)
CREATE TABLE vector_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    sentence_index INTEGER NOT NULL,
    embedding vector(384) NOT NULL, -- all-MiniLM-L6-v2 dimensions
    text TEXT NOT NULL,
    speaker_id VARCHAR(100) REFERENCES speakers(canonical_id),
    timestamp_seconds INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_vector_embeddings_video_id ON vector_embeddings(video_id);
CREATE INDEX idx_vector_embeddings_sentence ON vector_embeddings(sentence_index);

-- Create vector index for semantic search
CREATE INDEX idx_vector_embeddings_embedding ON vector_embeddings
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Chat Sessions (anonymous users)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(50) UNIQUE NOT NULL,
    user_id VARCHAR(50) NOT NULL, -- Anonymous UUID from client
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_session_id ON sessions(session_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_created ON sessions(created_at DESC);

-- Session Messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' | 'assistant'
    content TEXT NOT NULL,
    structured_response JSONB, -- For assistant responses
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
```

---

## Project Structure

```
yuhheardem/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Dependency injection
│   └── middleware.py           # Custom middleware
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py             # Chat/query endpoints
│   │   ├── videos.py           # Video management
│   │   ├── sessions.py         # Session management
│   │   ├── search.py           # Search endpoints
│   │   └── admin.py            # Admin endpoints
│   └── schemas.py              # Pydantic models for API
│
├── core/
│   ├── __init__.py
│   ├── database.py             # Database connection and session
│   ├── security.py             # (Future) Security utilities
│   └── logging_config.py       # Logging configuration
│
├── models/
│   ├── __init__.py
│   ├── video.py                # Video ORM model
│   ├── speaker.py              # Speaker ORM model
│   ├── entity.py               # Entity ORM model
│   ├── relationship.py         # Relationship ORM model
│   ├── legislation.py          # Legislation ORM model
│   ├── session.py              # Session ORM model
│   ├── message.py              # Message ORM model
│   └── mention.py              # Mention ORM model
│
├── services/
│   ├── __init__.py
│   ├── transcription.py        # Video transcription service
│   ├── order_paper.py          # Order paper processing
│   ├── entity_extraction.py   # Entity/relationship extraction
│   ├── parliamentary_agent.py # Agentic RAG query system
│   ├── search.py               # Hybrid search service
│   ├── session_manager.py      # Session management
│   ├── speaker_matcher.py      # Speaker deduplication
│   ├── embeddings.py           # Vector embeddings
│   └── scraper.py              # Legislation scraping
│
├── parsers/
│   ├── __init__.py
│   ├── order_paper_parser.py   # Order paper PDF parser
│   ├── video_parser.py         # Video transcript parser
│   └── legislation_parser.py  # Legislation scraper/parser
│
├── storage/
│   ├── __init__.py
│   ├── entity_store.py         # Entity persistence
│   ├── speaker_store.py        # Speaker persistence
│   ├── relationship_store.py   # Relationship persistence
│   └── vector_store.py          # Vector search (pgvector)
│
├── static/
│   ├── css/
│   │   └── styles.css          # Custom styles
│   ├── js/
│   │   └── app.js              # Frontend application logic
│   └── index.html              # Main HTML template
│
├── templates/
│   └── index.html              # Alternative: Jinja2 template
│
├── scripts/
│   ├── transcribe_video.py     # Video transcription script
│   ├── extract_entities.py     # Entity extraction script
│   ├── process_order_paper.py  # Order paper processing
│   ├── index_vectors.py        # Build vector index
│   ├── scrape_legislation.py   # Scrape legislation
│   └── init_db.py              # Database initialization
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_api/
│   ├── test_services/
│   ├── test_parsers/
│   └── test_models/
│
├── migrations/                 # Alembic migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── docs/
│   └── ARCHITECTURE.md         # Architecture documentation
│
├── alembic.ini                 # Alembic configuration
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── .env                        # Local environment (gitignored)
├── docker-compose.yml          # Docker configuration (optional)
├── Dockerfile                  # Docker image (optional)
└── README.md                   # Project documentation
```

---

## Implementation Plan (4-6 Weeks)

### Week 1: Foundation Setup

**Goal**: Project scaffolding, database setup, and basic infrastructure

**Tasks**:

1. **Day 1-2: Project Initialization**
   - [ ] Initialize Git repository
   - [ ] Set up Python virtual environment
   - [ ] Create project structure (all directories)
   - [ ] Create `requirements.txt` with all dependencies
   - [ ] Set up `pytest.ini` with test markers
   - [ ] Create `.env.example` with all environment variables
   - [ ] Set up `.gitignore` (Python + IDE + sensitive files)

2. **Day 3-4: Database Setup**
   - [ ] Design complete database schema (as above)
   - [ ] Create SQLAlchemy ORM models for all tables
   - [ ] Set up Alembic for database migrations
   - [ ] Create initial migration
   - [ ] Write database connection utilities (`core/database.py`)
   - [ ] Test database connectivity locally

3. **Day 5: Basic FastAPI Setup**
   - [ ] Create FastAPI application (`app/main.py`)
   - [ ] Set up CORS middleware
   - [ ] Create health check endpoint (`/health`)
   - [ ] Set up logging configuration
   - [ ] Configure environment variable loading
   - [ ] Write basic tests for application startup

4. **Day 6-7: Testing Infrastructure**
   - [ ] Set up test database (Docker or separate instance)
   - [ ] Create Pytest fixtures for database sessions
   - [ ] Create test factories for model creation
   - [ ] Write integration tests for database operations
   - [ ] Set up CI/CD pipeline (GitHub Actions or similar)

**Deliverables**:
- Running FastAPI application
- Database schema migrated
- Test suite infrastructure in place
- CI/CD pipeline passing

---

### Week 2: Core Services

**Goal**: Implement core data processing services from experimental rewrite

**Tasks**:

1. **Day 1-2: Order Paper Processing**
   - [ ] Port `order_paper_parser.py` from yuhheardem2
   - [ ] Adapt to use PostgreSQL storage instead of JSON files
   - [ ] Implement speaker deduplication with fuzzy matching
   - [ ] Add caching based on PDF hash
   - [ ] Write comprehensive tests (unit + integration)
   - [ ] Test with real order paper PDFs

2. **Day 3-4: Video Transcription**
   - [ ] Port `video_transcript.py` from yuhheardem2
   - [ ] Implement chunking for long videos
   - [ ] Integrate order paper context for speaker attribution
   - [ ] Save transcripts to PostgreSQL
   - [ ] Write tests with mock Gemini API
   - [ ] Test with real YouTube videos

3. **Day 5-6: Entity Extraction**
   - [ ] Port `entity_extractor.py` from yuhheardem2
   - [ ] Implement two-pass extraction (entities + relationships)
   - [ ] Integrate spaCy preprocessor
   - [ ] Save entities and relationships to PostgreSQL
   - [ ] Write tests for extraction logic
   - [ ] Test with sample transcripts

4. **Day 7: Vector Embeddings**
   - [ ] Port `embeddings.py` service
   - [ ] Implement batch embedding generation
   - [ ] Store embeddings in pgvector
   - [ ] Create vector similarity search function
   - [ ] Write tests for embedding generation
   - [ ] Benchmark embedding performance

**Deliverables**:
- Order paper processing service working
- Video transcription service working
- Entity extraction service working
- Vector embeddings service working
- All services with comprehensive tests

---

### Week 3: API Layer

**Goal**: Build REST API and chat interface

**Tasks**:

1. **Day 1-2: Video Management API**
   - [ ] Implement POST /videos (add new video for processing)
   - [ ] Implement GET /videos (list all videos with pagination)
   - [ ] Implement GET /videos/{id} (get video details)
   - [ ] Implement GET /videos/{id}/transcript (get transcript)
   - [ ] Add filtering by chamber, date range
   - [ ] Write API tests

2. **Day 3: Search API**
   - [ ] Implement GET /search (hybrid vector + text search)
   - [ ] Implement GET /search/entities (entity search)
   - [ ] Implement GET /search/speakers (speaker search)
   - [ ] Add query parameters for filters (chamber, date, type)
   - [ ] Write API tests with sample data

3. **Day 4-5: Parliamentary Agent**
   - [ ] Port `parliamentary_agent.py` from yuhheardem2
   - [ ] Implement function calling tools (find_entity, get_relationships, etc.)
   - [ ] Integrate with PostgreSQL storage
   - [ ] Implement multi-hop reasoning
   - [ ] Write tests for agent behavior
   - [ ] Test with sample queries

4. **Day 6-7: Chat API**
   - [ ] Implement POST /api/query (process query, return structured response)
   - [ ] Implement POST /api/query/stream (SSE streaming)
   - [ ] Implement GET /session/{id} (get session details)
   - [ ] Implement GET /session/{id}/messages (get message history)
   - [ ] Implement POST /session/{id}/archive (archive session)
   - [ ] Add session management service
   - [ ] Write API tests

**Deliverables**:
- Complete REST API with all endpoints
- Parliamentary agent working with function calling
- Chat API with streaming support
- API documentation (OpenAPI/Swagger)
- All API endpoints tested

---

### Week 4: Frontend & Integration

**Goal**: Port frontend and integrate with API

**Tasks**:

1. **Day 1-2: Frontend Setup**
   - [ ] Copy HTML template from original site
   - [ ] Copy CSS styles (Tailwind + custom)
   - [ ] Copy JavaScript app.js from original site
   - [ ] Update API endpoints to match new backend
   - [ ] Test static file serving
   - [ ] Verify basic functionality works

2. **Day 3: Chat Interface**
   - [ ] Connect chat UI to `/api/query/stream` endpoint
   - [ ] Implement SSE handling for streaming responses
   - [ ] Display structured response cards
   - [ ] Implement follow-up suggestions
   - [ ] Add error handling and reconnection logic
   - [ ] Test with real queries

3. **Day 4: Graph Visualization**
   - [ ] Port D3.js visualization from original site
   - [ ] Connect to session graph API endpoint
   - [ ] Implement interactive node/edge exploration
   - [ ] Add tooltips and metadata display
   - [ ] Test visualization with sample data

4. **Day 5: Session Management**
   - [ ] Implement session restoration on page reload
   - [ ] Store user_id and session_id in sessionStorage
   - [ ] Handle session creation on first query
   - [ ] Implement clear chat functionality
   - [ ] Add connection status indicator
   - [ ] Test session persistence

5. **Day 6-7: End-to-End Testing**
   - [ ] Write end-to-end tests with Playwright or Cypress
   - [ ] Test complete user flows (query, view results, explore graph)
   - [ ] Test error scenarios (network failures, API errors)
   - [ ] Load test with concurrent queries
   - [ ] Performance testing
   - [ ] Fix any bugs found

**Deliverables**:
- Working frontend UI matching original
- Chat interface with streaming
- Graph visualization working
- Complete end-to-end user flows tested
- Performance benchmarks

---

### Week 5: Polish & Deployment

**Goal**: Prepare for production deployment

**Tasks**:

1. **Day 1-2: Monitoring & Logging**
   - [ ] Add structured logging to all services
   - [ ] Set up log aggregation (or simple file rotation)
   - [ ] Add metrics collection (Prometheus or simple counters)
   - [ ] Create health check endpoint with database status
   - [ ] Add error tracking (or at least comprehensive error logging)
   - [ ] Test monitoring setup

2. **Day 3: Configuration Management**
   - [ ] Separate development and production configurations
   - [ ] Create production `.env` template
   - [ ] Document all configuration options
   - [ ] Add configuration validation on startup
   - [ ] Test with production-like configuration

3. **Day 4: Database Backups**
   - [ ] Set up automated PostgreSQL backups (pg_dump)
   - [ ] Configure WAL archiving for point-in-time recovery
   - [ ] Test backup and restore procedures
   - [ ] Document backup/restore process
   - [ ] Verify backup retention policy

4. **Day 5: Deployment Infrastructure**
   - [ ] Create Dockerfile (if using Docker)
   - [ ] Create docker-compose.yml for local development
   - [ ] Write systemd service file (if not using Docker)
   - [ ] Configure Nginx reverse proxy
   - [ ] Set up SSL certificates (Let's Encrypt)
   - [ ] Create deployment documentation

5. **Day 6-7: Deployment to VPS**
   - [ ] Set up VPS (provision server, install dependencies)
   - [ ] Configure PostgreSQL with pgvector
   - [ ] Deploy application to VPS
   - [ ] Configure Nginx and SSL
   - [ ] Test all endpoints in production
   - [ ] Monitor for issues for 24 hours
   - [ ] Document deployment process

**Deliverables**:
- Application deployed to VPS
- SSL configured
- Automated backups in place
- Monitoring and logging working
- Deployment documentation complete

---

### Week 6: Data Ingestion & Final Polish

**Goal**: Ingest real data and finalize MVP

**Tasks**:

1. **Day 1-2: Order Paper Ingestion**
   - [ ] Gather order paper PDFs for recent sessions
   - [ ] Batch process order papers
   - [ ] Verify speaker deduplication
   - [ ] Resolve any ambiguous matches
   - [ ] Load into database

2. **Day 3-4: Video Ingestion**
   - [ ] Identify YouTube videos to process
   - [ ] Batch transcribe videos (start with 5-10 sessions)
   - [ ] Monitor transcription quality
   - [ ] Extract entities and relationships
   - [ ] Generate vector embeddings
   - [ ] Index all data

3. **Day 5: Legislation Scraping**
   - [ ] Scrape all bills/resolutions from parliament website
   - [ ] Store in legislation table
   - [ ] Link to related entities
   - [ ] Verify data quality

4. **Day 6: Testing with Real Data**
   - [ ] Test search functionality with real data
   - [ ] Test chat queries with real data
   - [ ] Test graph visualization with real data
   - [ ] Verify citation accuracy
   - [ ] Fix any issues found

5. **Day 7: Final Polish**
   - [ ] Performance optimization (query tuning, indexing)
   - [ ] UI improvements (loading states, error messages)
   - [ ] Documentation update
   - [ ] Known issues list
   - [ ] Future enhancements documentation

**Deliverables**:
- MVP with real data loaded
- All core features working
- Performance acceptable
- Documentation complete
- Ready for public launch

---

## API Specification

### Chat & Query Endpoints

```python
POST /api/query
Request:
{
    "query": str,              # User's question
    "user_id": str,            # Anonymous UUID from client
    "session_id": str | None   # Session ID (if continuing)
}

Response:
{
    "session_id": str,
    "user_id": str,
    "message_id": str,
    "status": "success" | "error",
    "message": str | None,     # Error message if status is error
    "structured_response": {
        "intro_message": str,
        "response_cards": [
            {
                "summary": str,
                "details": str  # Markdown formatted
            }
        ],
        "follow_up_suggestions": [str]
    }
}

POST /api/query/stream
Request: Same as /api/query
Response: Server-Sent Events stream
Event: 'thinking' - "Thinking..." indicator
Event: 'response' - Final response (same format as /api/query)
Event: 'error' - Error message
```

### Video Endpoints

```python
GET /videos
Query Parameters:
    - chamber: 'senate' | 'house' | None
    - date_from: YYYY-MM-DD
    - date_to: YYYY-MM-DD
    - page: int (default 1)
    - per_page: int (default 20)

Response:
{
    "videos": [
        {
            "id": UUID,
            "youtube_id": str,
            "title": str,
            "chamber": str,
            "session_date": date,
            "sitting_number": str | None,
            "duration_seconds": int | None,
            "transcript_processed_at": datetime | None
        }
    ],
    "total": int,
    "page": int,
    "per_page": int
}

GET /videos/{video_id}
Response:
{
    "id": UUID,
    "youtube_id": str,
    "youtube_url": str,
    "title": str,
    "chamber": str,
    "session_date": date,
    "sitting_number": str | None,
    "duration_seconds": int | None,
    "transcript": {
        "session_title": str,
        "agenda_items": [...]
    },
    "created_at": datetime,
    "updated_at": datetime
}

POST /videos
Request:
{
    "youtube_url": str,
    "order_paper_path": str | None,
    "process": bool = True  # Whether to process immediately
}

Response:
{
    "video_id": UUID,
    "status": "queued" | "processing" | "completed" | "error",
    "message": str
}
```

### Search Endpoints

```python
GET /search
Query Parameters:
    - query: str
    - type: 'all' | 'entities' | 'transcripts' | 'speakers'
    - chamber: 'senate' | 'house' | None
    - date_from: YYYY-MM-DD
    - date_to: YYYY-MM-DD
    - limit: int (default 10)

Response:
{
    "results": [
        {
            "type": "entity" | "transcript" | "speaker",
            "id": str,
            "title": str,
            "summary": str,
            "relevance_score": float,
            "metadata": {...}
        }
    ],
    "total": int
}

GET /search/entities
Query Parameters:
    - query: str
    - type: str | None  # Filter by entity type
    - limit: int (default 20)

Response:
{
    "entities": [
        {
            "entity_id": str,
            "entity_type": str,
            "name": str,
            "canonical_name": str,
            "description": str,
            "importance_score": float
        }
    ],
    "total": int
}

GET /search/speakers
Query Parameters:
    - query: str
    - chamber: 'senate' | 'house' | None
    - limit: int (default 20)

Response:
{
    "speakers": [
        {
            "canonical_id": str,
            "name": str,
            "title": str,
            "role": str,
            "chamber": str
        }
    ],
    "total": int
}
```

### Session Endpoints

```python
GET /session/{session_id}
Response:
{
    "session_id": str,
    "user_id": str,
    "created_at": datetime,
    "last_updated": datetime,
    "archived": bool,
    "message_count": int
}

GET /session/{session_id}/messages
Response:
{
    "messages": [
        {
            "id": str,
            "role": "user" | "assistant",
            "content": str,
            "structured_response": {...} | None,
            "created_at": datetime
        }
    ]
}

POST /session/{session_id}/archive
Response:
{
    "status": "success",
    "message": "Session archived"
}

GET /session/{session_id}/graph
Response:
{
    "nodes": [
        {
            "id": str,
            "label": str,
            "type": str,
            "metadata": {...}
        }
    ],
    "edges": [
        {
            "source": str,
            "target": str,
            "relation": str,
            "sentiment": str
        }
    ]
}
```

---

## Testing Strategy

### Test Pyramid

```
                    E2E Tests (5%)
                   ─────────────────
                  Browser testing
                  (Playwright/Cypress)

                Integration Tests (20%)
               ────────────────────────
              API endpoints, database
              operations, external services

            Unit Tests (75%)
           ────────────────────────────
          Individual functions, classes,
          models, parsers, services
```

### Test Categories

1. **Unit Tests** (pytest markers: `unit`)
   - Model validation
   - Service methods
   - Parser logic
   - Helper functions
   - Fuzzy matching

2. **Integration Tests** (pytest markers: `integration`)
   - Database operations
   - API endpoints
   - Service orchestration
   - External API integration (mocked)

3. **End-to-End Tests** (pytest markers: `e2e`)
   - Complete user flows
   - Multi-hop queries
   - Error scenarios

4. **Slow Tests** (pytest markers: `slow`)
   - Long-running operations
   - Large dataset processing
   - Performance benchmarks

5. **Expensive Tests** (pytest markers: `expensive`)
   - Tests requiring paid API calls (Gemini)
   - Only run manually or in nightly builds

### Test Coverage Targets

- **Unit Tests**: 90%+ coverage
- **Integration Tests**: 70%+ coverage
- **E2E Tests**: Critical user paths only
- **Overall**: 80%+ coverage (excluding expensive tests)

---

## Performance Optimization

### Database Optimization

1. **Indexing Strategy**:
   - All foreign keys indexed
   - Full-text search indexes on searchable fields
   - Vector index for pgvector (ivfflat)
   - Composite indexes for common query patterns

2. **Query Optimization**:
   - Use `EXPLAIN ANALYZE` to profile slow queries
   - Add appropriate indexes based on query patterns
   - Use `select_related` and `joinload` for eager loading
   - Implement pagination for large result sets

3. **Connection Pooling**:
   - Use SQLAlchemy async engine with connection pool
   - Configure appropriate pool size (default: 5-20 connections)
   - Use connection pool pre-ping for health checks

### Caching Strategy

1. **Application-Level Caching**:
   - Cache order paper parsing results (by PDF hash)
   - Cache speaker lookup results
   - Cache entity search results (TTL: 1 hour)
   - Use Redis if needed (or simple in-memory cache for MVP)

2. **Database-Level Caching**:
   - Enable PostgreSQL query cache
   - Materialized views for complex aggregations
   - Consider pg_stat_statements for query analysis

### API Optimization

1. **Response Compression**:
   - Enable gzip compression for API responses
   - Use FastAPI middleware for compression

2. **Async Processing**:
   - Use async/await for all I/O operations
   - Implement background task queue for video processing
   - Use `asyncpg` for async PostgreSQL driver

3. **Rate Limiting**:
   - Implement rate limiting on API endpoints
   - Use `slowapi` or custom middleware

---

## Deployment Strategy

### Development Environment

```bash
# Local development with Docker
docker-compose up -d

# Or manual setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Production Deployment

**Option 1: Docker Compose (Simple)**
```bash
# On VPS
git clone <repo>
cd yuhheardem
cp .env.example .env
# Edit .env with production values
docker-compose up -d
```

**Option 2: Systemd (More Control)**
```bash
# Install dependencies
sudo apt install postgresql-16-pgvector python3.13
git clone <repo>
cd yuhheardem
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure database
sudo -u postgres createdb yuhheardem
sudo -u postgres psql yuhheardem < init_db.sql
alembic upgrade head

# Configure systemd
sudo cp yuhheardem.service /etc/systemd/system/
sudo systemctl enable yuhheardem
sudo systemctl start yuhheardem
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name yuhheardem.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yuhheardem.com;

    ssl_certificate /etc/letsencrypt/live/yuhheardem.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yuhheardem.com/privkey.pem;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
    }

    location /static/ {
        alias /path/to/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Risk Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Gemini API rate limits | Medium | High | Implement caching, batching, retry logic |
| pgvector performance issues | Low | Medium | Test with real data, optimize indexes |
| Video transcription costs | Medium | High | Monitor usage, implement cost controls |
| Data quality issues | Medium | Medium | Manual verification workflow, fuzzy matching |
| Database scaling issues | Low | Medium | Design for scale from start, monitor metrics |

### Timeline Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Unexpected technical challenges | Medium | High | Prioritize MVP features, defer nice-to-haves |
| API integration issues | Low | Medium | Mock APIs for development, integrate early |
| Testing taking longer than expected | Medium | Medium | Write tests continuously, not at end |
| Deployment issues | Low | High | Test deployment in staging environment first |

### Mitigation Strategies

1. **Early API Integration**: Integrate Gemini API early to understand limitations
2. **Continuous Testing**: Write tests alongside code, not as afterthought
3. **Incremental Delivery**: Deliver working features every week
4. **Staging Environment**: Test deployment in staging before production
5. **Monitoring**: Set up monitoring from day 1 to catch issues early
6. **Cost Monitoring**: Track Gemini API costs from start

---

## Future Enhancements (Post-MVP)

1. **Authentication**: Add user accounts for saved preferences and history
2. **Admin UI**: Web interface for data verification and management
3. **Video Upload**: Direct video upload (not just YouTube)
4. **Live Transcription**: Real-time transcription of ongoing sessions
5. **Mobile App**: Native mobile applications
6. **Analytics**: Usage analytics and popular queries
7. **Export**: Export search results, transcripts, graphs
8. **Multi-language**: Support multiple languages
9. **API for Developers**: Public API for third-party integrations
10. **Improved Speaker Recognition**: Voice fingerprinting for better attribution

---

## Success Criteria

MVP is successful when:

1. ✅ Users can ask natural language questions about parliamentary sessions
2. ✅ System returns accurate answers with citations (video, timestamp, quote)
3. ✅ Users can explore knowledge graph interactively
4. ✅ Search returns relevant results (entities, transcripts, speakers)
5. ✅ System can process new videos and extract entities automatically
6. ✅ API responds in <3 seconds for typical queries
7. ✅ System handles 10+ concurrent users without degradation
8. ✅ Application is deployed and accessible via HTTPS
9. ✅ Database backups are automated and tested
10. ✅ All critical code paths have tests (80%+ coverage)

---

## References

- **Architecture Analysis**: `docs/ARCHITECTURE_ANALYSIS.md`
- **Experimental Rewrite**: `../yuhheardem2/`
- **Original Site**: `../YuhHearDem.orig/`
- **Gemini API**: https://ai.google.dev/gemini-api/docs
- **FastAPI**: https://fastapi.tiangolo.com/
- **pgvector**: https://github.com/pgvector/pgvector
- **Alembic**: https://alembic.sqlalchemy.org/

---

## Appendix: Commands Reference

### Development Commands

```bash
# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest                          # All tests
pytest -m unit                  # Unit tests only
pytest -m integration           # Integration tests only
pytest -m "not slow"            # Skip slow tests
pytest --cov=app                # With coverage

# Database migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
alembic history

# Linting and formatting
ruff check app/                 # Lint
ruff check --fix app/           # Auto-fix
ruff format app/                # Format

# Type checking
mypy app/
```

### Production Commands

```bash
# Start application
systemctl start yuhheardem
systemctl stop yuhheardem
systemctl restart yuhheardem
systemctl status yuhheardem

# View logs
journalctl -u yuhheardem -f

# Database backup
pg_dump -U postgres yuhheardem > backup_$(date +%Y%m%d).sql

# Database restore
psql -U postgres yuhheardem < backup_20250202.sql
```

### Data Processing Scripts

```bash
# Transcribe a video
python scripts/transcribe_video.py --url https://youtube.com/watch?v=XXX --order-paper data/order_papers/session.pdf

# Extract entities from transcript
python scripts/extract_entities.py --transcript data/processed/transcript_xxx.json

# Process order papers
python scripts/process_order_paper.py data/order_papers/session.pdf

# Build vector index
python scripts/index_vectors.py

# Scrape legislation
python scripts/scrape_legislation.py
```

---

**Document Version**: 1.0
**Last Updated**: 2025-02-02
**Author**: Planning Document
