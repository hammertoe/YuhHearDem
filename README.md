# YuhHearDem

Barbados Parliamentary Knowledge Graph - A comprehensive system for analyzing and searching parliamentary proceedings, speeches, and related documents.

## Overview

YuhHearDem uses advanced NLP techniques to:

- Extract and parse parliamentary documents (Hansard)
- Process speaker information and metadata
- Generate vector embeddings for semantic search
- Provide a fast, searchable knowledge graph
- Enable discovery of parliamentary information

## Tech Stack

- **Ingestion**: Python 3.13 scripts (async)
- **Database**: PostgreSQL 16 with pgvector extension
- **NLP**: spaCy, Google Gemini API, sentence-transformers
- **Video Processing**: YouTube URLs processed directly by Gemini API (no downloads)

Note: The web UI and API have been moved to a separate package. This repository focuses on scraping and ingestion tooling.

## Quick Start

### Get Started Fast (Ingest Data)

**New!** Complete ingestion pipeline now available. See [QUICKSTART.md](./QUICKSTART.md) for detailed instructions.

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY

# 2. Start database
docker-compose up -d

# 3. Initialize schema
python -c "import asyncio; from core.database import init_db; asyncio.run(init_db())"

# 4. Ingest data (single video)
python scripts/ingest_video.py --url 'https://www.youtube.com/watch?v=VIDEO_ID' --no-thinking

# Or ingest from mapping file
python scripts/ingest_video.py --mapping data/video_mapping.json
```

### Local Development

```bash
# Clone repository
git clone git@github.com:hammertoe/YuhHearDem.git
cd YuhHearDem

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize schema
python -c "import asyncio; from core.database import init_db; asyncio.run(init_db())"
```

## Project Structure

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
├── tests/              # Test suite
├── .env.example        # Environment template
├── README.md           # Project overview and quick start
├── QUICKSTART.md       # Step-by-step local setup
├── USAGE.md            # Usage examples
└── requirements.txt     # Python dependencies
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=models --cov=parsers --cov=services --cov=scripts --cov-report=html

# Run specific test
pytest tests/test_specific_file.py::test_function
```

### Code Quality

```bash
# Lint code
ruff check .

# Format code
ruff format .

# Type checking
mypy core/ models/ parsers/ services/ scripts/

# Run pre-commit hooks
pre-commit run --all-files
```

### Database Schema

Schema is created directly from SQLAlchemy models.

```bash
# Initialize schema on a fresh database
python -c "import asyncio; from core.database import init_db; asyncio.run(init_db())"

# Reset schema (development only, drops all data)
python scripts/reset_db.py
```

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/yuhheardem
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# API Keys
GOOGLE_API_KEY=your_api_key

# Google Gemini
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_TEMPERATURE=0.3

# Application
APP_ENV=development|production
DEBUG=True|False
LOG_LEVEL=INFO

# Vector Search
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# spaCy
SPACY_MODEL=en_core_web_trf

# Fuzzy Matching
FUZZY_MATCH_THRESHOLD=85

# Cache
CACHE_TTL_SECONDS=3600
```

## Key Features

### Video Ingestion

- **Auto-detection**: Automatically extracts session date, chamber, and sitting number from video metadata
- **Multi-method metadata**: Uses Invidious, Piped, oEmbed, and RSS with fallback to YouTube watch page
- **Fast ingestion**: `--no-thinking` flag disables Gemini thinking mode for faster processing
- **YouTube URLs only**: Videos are never downloaded - URLs passed directly to Gemini API
- **Stable IDs**: All IDs are deterministic and stable across re-ingestion
- **Duplicate detection**: Skips existing videos and segments automatically

### Knowledge Graph Extraction

- Two-pass extraction (entities first, then relationships)
- Explicit evidence linking to transcript segments
- Entity deduplication with fuzzy matching
- Relationship confidence scoring

## Documentation

- [AGENTS.md](./AGENTS.md) - Comprehensive codebase guide with code map (start here for development)
- [Scripts Documentation](./scripts/README.md) - Data ingestion scripts guide

### Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [AGENTS.md](./AGENTS.md) | Codebase guide with code map | AI agents, developers |
| [README.md](./README.md) | Project overview and quick start | Everyone |
| [QUICKSTART.md](./QUICKSTART.md) | Step-by-step local setup | New users |
| [USAGE.md](./USAGE.md) | Script usage and examples | Users |
| [scripts/README.md](./scripts/README.md) | Data ingestion scripts guide | Users |
| [docs/INGESTOR_DESIGN.md](./docs/INGESTOR_DESIGN.md) | Schema design and data flow | Developers |

## Important Notes

### No Video Downloads Policy

At no point should this system download video files. All video processing must use YouTube URLs directly with the Gemini API. This approach:

- Saves disk space
- Avoids bandwidth costs
- Prevents copyright concerns
- Uses Gemini's native video understanding capabilities

### Re-ingestion Support

The system supports re-ingesting the same video:

- Existing videos are automatically skipped
- Existing transcript segments are deleted and replaced
- Relationship evidence is replaced with new data
- Segment IDs use counter suffixes (`_c01`, `_c02`) when timecodes are missing to prevent duplicates

## Contributing

1. Fork repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Write tests for new features
- Update documentation as needed
- Keep commits atomic and well-described

## License

[MIT License](LICENSE)

## Support

For issues, questions, or contributions:

- Open an issue on GitHub
- Check existing documentation

## Acknowledgments

- Built for Barbados parliamentary data
- Uses open-source NLP libraries
- Inspired by similar knowledge graph projects
