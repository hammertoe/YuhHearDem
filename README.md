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
- **NLP**: spaCy, sentence-transformers
- **Search**: Vector similarity search with fuzzy matching

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

# 3. Run migrations
alembic upgrade head

# 4. Ingest data
# Option A: Full pipeline (automatic)
python scripts/run_full_ingestion.py --chamber house --max-papers 10

# Option B: Manual step-by-step
# See scripts/README.md for details
```

### Local Development

```bash
# Clone the repository
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

# Run migrations
alembic upgrade head

# Ingest videos (YouTube URLs processed directly by Gemini)
python scripts/ingest_video.py --mapping data/video_mapping.json
```

## Project Structure

```
YuhHearDem/
├── core/               # Shared utilities
├── data/               # Raw data files
├── docs/               # Documentation
├── migrations/         # Database migrations
├── models/             # SQLAlchemy models
├── parsers/            # Document parsers
├── processed/          # Processed data
├── scripts/            # Scraping + ingestion tools
├── services/           # Business logic
├── storage/            # Persistent storage
├── tests/              # Test suite
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

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```


## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/yuhheardem

# API Keys
GOOGLE_API_KEY=your_api_key

# Application
APP_ENV=development|production
DEBUG=True|False

# Vector Search
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# Fuzzy Matching
FUZZY_MATCH_THRESHOLD=85
```

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
| [scripts/README.md](./scripts/README.md) | Data ingestion guide | Users |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
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

- Built for the Barbados parliamentary data
- Uses open-source NLP libraries
- Inspired by similar knowledge graph projects
