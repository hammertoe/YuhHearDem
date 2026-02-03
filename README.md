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

- **Backend**: FastAPI with Python 3.13
- **Database**: PostgreSQL 16 with pgvector extension
- **NLP**: spaCy, sentence-transformers
- **Search**: Vector similarity search with fuzzy matching
- **Frontend**: To be implemented
- **Deployment**: Docker with blue-green strategy
- **Reverse Proxy**: nginx with Let's Encrypt SSL

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
python scripts/run_full_ingestion.py --download-videos

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

# Start application
uvicorn app.main:app --reload
```

### Docker (Local)

```bash
# Build the image
docker build -t yuhheardem:dev .

# Run the container
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL="postgresql+asyncpg://postgres:password@host.docker.internal:5432/yuhheardem" \
  -e GOOGLE_API_KEY="your_key" \
  yuhheardem:dev
```

### Production Deployment

See [Deployment Quickstart](./docs/DEPLOYMENT_QUICKSTART.md) for production deployment instructions.

## Project Structure

```
YuhHearDem/
├── app/                 # FastAPI application
│   ├── api/            # API routes and schemas
│   ├── core/           # Core functionality
│   ├── models/         # SQLAlchemy models
│   ├── parsers/        # Document parsers
│   ├── services/       # Business logic
│   ├── static/         # Static assets
│   └── templates/      # HTML templates
├── core/               # Shared utilities
├── data/               # Raw data files
├── docs/               # Documentation
├── migrations/         # Database migrations
├── processed/          # Processed data
├── storage/            # Persistent storage
├── tests/              # Test suite
├── deploy/             # Deployment scripts
├── Dockerfile          # Docker image definition
└── requirements.txt     # Python dependencies
```

## API Endpoints

### Health

- `GET /health` - Health check endpoint
- `GET /` - Root endpoint with application info
- `GET /api` - API information

### Parliamentary Search

- `GET /api/speeches` - Search parliamentary speeches
- `GET /api/speakers` - List and search speakers
- `GET /api/documents` - Search documents

### Vector Search

- `POST /api/search` - Semantic search using embeddings
- `GET /api/similar` - Find similar content

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=core --cov-report=html

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
mypy app/ core/

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

## Deployment

### Production Deployment

YuhHearDem uses a blue-green deployment strategy on the `yhd` server:

- **Blue-green deployment** for zero-downtime releases
- **Docker containers** for isolation and reproducibility
- **PostgreSQL with pgvector** for vector search
- **nginx** as reverse proxy with SSL
- **GitHub Actions** for automated builds and deployments

For detailed deployment instructions, see:

- [Deployment Quickstart](./docs/DEPLOYMENT_QUICKSTART.md) - Get started with production deployment
- [Deployment Guide](./docs/deployment.md) - Comprehensive deployment documentation

### Manual Deployment

```bash
# SSH to production server
ssh yhd

# Deploy latest version
cd /opt/yuhheardem
sudo ./deploy/deploy.sh latest

# Check deployment status
sudo ./deploy/deploy.sh status

# Rollback if needed
sudo ./deploy/deploy.sh rollback
```

### Automated Deployment

Every push to `main` triggers:

1. Build Docker image
2. Push to GitHub Container Registry
3. SSH to production server
4. Deploy new version

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
CORS_ORIGINS=["http://localhost:3000"]

# Vector Search
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# Fuzzy Matching
FUZZY_MATCH_THRESHOLD=85
```

## Documentation

- [Architecture Analysis](./docs/ARCHITECTURE_ANALYSIS.md) - System architecture and design decisions
- [Rebuild Plan](./docs/REBUILD_PLAN.md) - Technical implementation details
- [Deployment Quickstart](./docs/DEPLOYMENT_QUICKSTART.md) - Get started with deployment
- [Deployment Guide](./docs/deployment.md) - Comprehensive deployment documentation

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
- Review deployment status on server

## Acknowledgments

- Built for the Barbados parliamentary data
- Uses open-source NLP libraries
- Inspired by similar knowledge graph projects
