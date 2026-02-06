# YuhHearDem Production Setup Guide

This guide walks through setting up YuhHearDem on the `yhd` production server.

## Prerequisites

- SSH access to `yhd` server
- sudo or PostgreSQL superuser access
- Python 3.13+ installed on the server
- A working Google Gemini API key

## Quick Start

1. **Copy the repository to yhd server:**
   ```bash
   # On your local machine
   rsync -avz --exclude='venv' --exclude='__pycache__' \
     /Users/matt/Development/YuhHearDem/ yhd@yhd:/opt/yuhheardem/
   ```

2. **Run the setup script:**
   ```bash
   # SSH into yhd server
   ssh yhd@yhd
   cd /opt/yuhheardem
   sudo bash scripts/setup_prod_db.sh
   ```

3. **Configure your API key:**
   ```bash
   # Edit .env file
   nano .env

   # Update this line:
   GOOGLE_API_KEY=your_actual_production_api_key_here
   ```

4. **Activate and test:**
   ```bash
   source venv/bin/activate
   python3 -c "import asyncio; from core.database import get_engine; asyncio.run(get_engine().dispose())"
   ```

## What the Setup Script Does

The `scripts/setup_prod_db.sh` script automatically:

1. ✅ Checks PostgreSQL is installed
2. ✅ Installs and enables the `pgvector` extension
3. ✅ Creates PostgreSQL user and database
4. ✅ Creates application directory at `/opt/yuhheardem`
5. ✅ Sets up Python 3.13+ virtual environment
6. ✅ Installs all dependencies from `requirements.txt`
7. ✅ Creates `.env` file from template
8. ✅ Initializes the database schema

## Manual Setup (Alternative)

If you prefer to set up manually instead of using the script:

### 1. Install PostgreSQL with pgvector

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib
```

**macOS (if developing locally):**
```bash
brew install pgvector postgresql
```

### 2. Create Database and User

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create user and database
CREATE USER postgres WITH PASSWORD 'YHD_9f3b7c2d5a8e1f6g';
CREATE DATABASE yuhheardem OWNER postgres;

# Connect to database
\c yuhheardem

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify extension
\dx vector
```

### 3. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` file:
```bash
cp .env.production.example .env
nano .env
```

Set your `GOOGLE_API_KEY`.

### 5. Initialize Database Schema

```bash
python3 -c "
import asyncio
from core.database import init_db

async def main():
    await init_db()
    print('Database initialized!')

asyncio.run(main())
"
```

## Database Connection Details

**Development (local):**
- Host: localhost
- Port: 5432
- Database: yuhheardem_test
- Password: YHD_9f3b7c2d5a8e1f6g

**Production (yhd):**
- Host: localhost
- Port: 5432
- Database: yuhheardem
- Password: YHD_9f3b7c2d5a8e1f6g
- User: postgres

Update `DATABASE_URL` in `.env` for external access:
```
DATABASE_URL=postgresql+asyncpg://postgres:YHD_9f3b7c2d5a8e1f6g@<EXTERNAL_IP>:5432/yuhheardem
```

## Running Ingestion

**Single video:**
```bash
source venv/bin/activate
python3 scripts/ingest_video.py \
  --url "https://www.youtube.com/watch?v=VIDEO_ID" \
  --session-date "YYYY-MM-DD" \
  --end-time 600 \
  --no-thinking
```

**From JSON mapping file:**
```bash
python3 scripts/ingest_video.py \
  --mapping data/video_mapping.json
```

**Order paper PDF:**
```bash
python3 scripts/ingest_order_paper.py data/papers/session_paper.pdf
```

## Troubleshooting

### Database Connection Issues

```bash
# Test PostgreSQL is running
sudo -u postgres psql -c "SELECT 1;"

# Test pgvector is installed
sudo -u postgres psql -c "SELECT extname FROM pg_extension WHERE extname='pgvector';"

# Restart PostgreSQL
sudo systemctl restart postgresql  # Linux
brew services restart postgresql  # macOS
```

### Python Issues

```bash
# Verify Python version
python3 --version  # Should be 3.13+

# Reinstall virtualenv
pip3 install --user --upgrade virtualenv
rm -rf venv
python3 -m venv venv
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R $USER:$USER /opt/yuhheardem

# Fix permissions
sudo chmod -R 755 /opt/yuhheardem/scripts
```

## Production vs Development

| Setting | Development | Production |
|----------|-------------|-------------|
| Database | yuhheardem_test | yuhheardem |
| Debug Mode | True | False |
| Logging | INFO | INFO |
| APP_ENV | development | production |

## Important Notes

⚠️ **Security:**
- Never commit `.env` with real API keys to git
- Use strong database passwords in production
- Consider using PostgreSQL SSL for remote connections

⚠️ **Performance:**
- Use `--no-thinking` flag to disable thinking mode (faster)
- Monitor PostgreSQL memory usage with large datasets
- Consider increasing `DATABASE_POOL_SIZE` for concurrent ingestion

⚠️ **Data Loss:**
- Production database will be wiped if you run setup script again
- Always backup before running: `pg_dump -U postgres yuhheardem > backup.sql`

## Support

For issues, check:
1. Application logs
2. PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql.log`
3. Database queries in SQLAlchemy echo mode (set `DEBUG=True` in .env)
