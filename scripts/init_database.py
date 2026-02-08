"""Initialize database with new schema.

This script creates all tables with the updated schema for the re-architected system.
Run this after making breaking changes to models.

Usage:
    python scripts/init_database.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import init_db, get_engine
from sqlalchemy import text


async def setup_extensions():
    """Set up required PostgreSQL extensions."""
    from core.database import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✓ pgvector extension enabled")


async def main():
    """Initialize database."""
    print("Setting up PostgreSQL extensions...")
    await setup_extensions()

    print("\nCreating database tables...")
    await init_db()
    print("✓ All tables created successfully")

    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
