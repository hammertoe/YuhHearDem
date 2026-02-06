#!/bin/bash
# Production Database Setup Script for YuhHearDem on yhd server
# Run this script as a user with PostgreSQL superuser privileges

set -e

echo "=========================================="
echo "YuhHearDem Production Database Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_USER="postgres"
DB_PASSWORD="YHD_9f3b7c2d5a8e1f6g"
DB_NAME="yuhheardem"
DB_PORT="5432"

echo -e "${GREEN}[1/8] Checking PostgreSQL installation...${NC}"
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL not found${NC}"
    echo "Please install PostgreSQL first:"
    echo "  sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

POSTGRES_VERSION=$(psql --version | awk '{print $3}')
echo -e "  Found PostgreSQL ${POSTGRES_VERSION}"
echo ""

echo -e "${GREEN}[2/8] Checking pgvector extension...${NC}"
if ! sudo -u postgres psql -c "SELECT extname FROM pg_extension WHERE extname='pgvector';" 2>/dev/null | grep -q pgvector; then
    echo -e "${YELLOW}pgvector extension not found${NC}"
    echo "Installing pgvector..."

    # Install pgvector
    if [ -f "/etc/os-release" ]; then
        # Ubuntu/Debian
        . /etc/os-release
        if [[ "$ID" == "ubuntu" ]]; then
            sudo apt-get update
            sudo apt-get install -y postgresql-$POSTGRES_VERSION-pgvector
        elif [[ "$ID" == "debian" ]]; then
            sudo apt-get update
            sudo apt-get install -y postgresql-pgvector
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew install pgvector
    fi

    # Enable extension
    echo -e "${YELLOW}Enabling pgvector extension for template1...${NC}"
    sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"

    # Restart PostgreSQL to load extension
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services restart postgresql
    else
        sudo systemctl restart postgresql
    fi

    echo -e "${GREEN}✓ pgvector installed and enabled${NC}"
else
    echo -e "${GREEN}✓ pgvector extension found${NC}"
fi
echo ""

echo -e "${GREEN}[3/8] Creating database user and database...${NC}"

# Create user if not exists
sudo -u postgres psql -c "DO \$\$$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
  END IF
COMMIT;
\$\$"

# Create database if not exists
sudo -u postgres psql -c "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}';" 2>/dev/null | grep -q 1 || \
    sudo -u postgres createdb -O ${DB_USER} ${DB_NAME}

echo -e "${GREEN}✓ Database '${DB_NAME}' created${NC}"
echo ""

echo -e "${GREEN}[4/8] Enabling pgvector extension...${NC}"
sudo -u postgres psql -d ${DB_NAME} -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo ""

echo -e "${GREEN}[5/8] Setting up Python environment...${NC}"

# Check if Python 3.13+ is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    echo "Please install Python 3.13+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo -e "  Found Python ${PYTHON_VERSION}"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 13 ]); then
    echo -e "${YELLOW}Warning: Python 3.13+ recommended, found ${PYTHON_VERSION}${NC}"
fi
echo ""

# Check if virtualenv exists
if ! command -v python3 -m venv &> /dev/null; then
    echo -e "${YELLOW}venv module not found${NC}"
    echo "Installing virtualenv..."
    pip3 install --user virtualenv
fi

echo ""
echo -e "${GREEN}[6/8] Setting up application directory...${NC}"

# Define application directory (adjust as needed)
APP_DIR="/opt/yuhheardem"

if [ ! -d "$APP_DIR" ]; then
    echo "Creating application directory at $APP_DIR"
    sudo mkdir -p $APP_DIR
    sudo chown $USER:$USER $APP_DIR
else
    echo -e "${GREEN}✓ Application directory exists${NC}"
fi

echo ""
echo -e "${GREEN}[7/8] Installing dependencies...${NC}"

# Create virtual environment if needed
if [ ! -d "$APP_DIR/venv" ]; then
    cd $APP_DIR
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate
    echo -e "${GREEN}✓ Virtual environment created and dependencies installed${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
    echo "To reinstall dependencies, remove $APP_DIR/venv and run this script again"
fi
echo ""

echo -e "${GREEN}[8/8] Initializing database schema...${NC}"

# Activate virtual environment and run initialization
cd $APP_DIR
source venv/bin/activate

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.production.example .env
    echo -e "${YELLOW}⚠  IMPORTANT: Edit .env and set your GOOGLE_API_KEY${NC}"
    echo ""
fi

# Initialize database schema
python3 -c "
import asyncio
from core.database import init_db

async def main():
    print('Initializing database schema...')
    await init_db()
    print('Database schema initialized successfully!')

asyncio.run(main())
"

deactivate

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Edit $APP_DIR/.env and set your GOOGLE_API_KEY"
echo ""
echo "2. Activate the virtual environment:"
echo "   cd $APP_DIR"
echo "   source venv/bin/activate"
echo ""
echo "3. Test the database connection:"
echo "   python3 -c \"import asyncio; from core.database import get_engine; asyncio.run(get_engine().dispose())\""
echo ""
echo "4. Run the ingestion pipeline:"
echo "   python3 scripts/ingest_video.py --url '<YOUTUBE_URL>' --session-date 'YYYY-MM-DD' --end-time 600 --no-thinking"
echo ""
echo -e "${GREEN}Database connection info:${NC}"
echo "  Host: localhost"
echo "  Port: ${DB_PORT}"
echo "  Database: ${DB_NAME}"
echo "  User: ${DB_USER}"
echo ""
echo -e "${YELLOW}To access from other servers:${NC}"
echo "  Update DATABASE_URL to: postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@<EXTERNAL_IP>:${DB_PORT}/${DB_NAME}"
